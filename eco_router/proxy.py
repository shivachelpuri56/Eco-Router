"""
Reverse proxy core — forwards requests to the carbon-selected region.

Security controls:
  - SSRF: target URLs come ONLY from settings.allowed_target_urls
  - Hop-by-hop headers are stripped before forwarding
  - Request body size is capped at MAX_REQUEST_BODY_SIZE
  - Upstream timeout enforced

Response headers added:
  X-Eco-Router-Region      — region that handled the request
  X-Carbon-Intensity       — carbon intensity of selected region (gCO2e/kWh)
  X-Request-Id             — UUID for this routing event
  X-Carbon-Data-Source     — mock | live | cached | stale
"""
from __future__ import annotations
import time
import uuid
from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException, Request, Response
from loguru import logger

from eco_router.carbon_cache import fetch_carbon_reading
from eco_router.config import HOP_BY_HOP_HEADERS, settings
from eco_router.decision_engine import NoAvailableRegionError, decision_engine
from eco_router.logging_config import emit_routing_event
from eco_router.schemas import RoutingDecision

if TYPE_CHECKING:
    from eco_router.main import AppState


async def _build_upstream_headers(request: Request) -> dict[str, str]:
    """Build safe header set for the upstream request."""
    headers = {}
    for name, value in request.headers.items():
        if name.lower() not in HOP_BY_HOP_HEADERS:
            headers[name] = value
    # Add forwarding metadata
    headers["X-Forwarded-For"] = (
        request.headers.get("X-Forwarded-For", request.client.host)
        if request.client
        else "unknown"
    )
    headers["X-Forwarded-Host"] = request.headers.get("host", "")
    return headers


async def forward_request(
    request: Request,
    path: str,
    app_state: "AppState",
) -> Response:
    """
    Main proxy entry point.
    1. Generate request ID
    2. Get current carbon readings from app state
    3. Run decision engine
    4. Forward to selected region
    5. Log + persist the routing event
    6. Return response with Eco-Router headers
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # ── Guard: body size ──────────────────────────────────────────────────────
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_body_size:
        raise HTTPException(
            status_code=413,
            detail=f"Request body exceeds {settings.max_request_body_size} bytes limit",
        )

    # ── Step 1: Get current carbon state ──────────────────────────────────────
    carbon_readings = dict(app_state.carbon_readings)
    health_status = dict(app_state.health_status)

    # Ensure we have readings for all regions (fetch on-demand if cache empty)
    regions = list(settings.regions.keys())
    for region in regions:
        if region not in carbon_readings:
            try:
                reading = await fetch_carbon_reading(region)
                carbon_readings[region] = reading
                app_state.carbon_readings[region] = reading
            except Exception as e:
                logger.warning(f"[Proxy] Failed to fetch carbon for {region}: {e}")

    # ── Step 2: Decision engine ────────────────────────────────────────────────
    try:
        decision: RoutingDecision = decision_engine.make_decision(
            carbon_readings=carbon_readings,
            health_status=health_status,
            request_id=request_id,
        )
    except NoAvailableRegionError as e:
        logger.error(f"[Proxy] No available region: {e}")
        _emit_failure_event(request_id, request, str(e), start_time, carbon_readings)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_available_region",
                "message": str(e),
                "request_id": request_id,
            },
        )

    # ── Step 3: Get target URL ─────────────────────────────────────────────────
    region_config = settings.regions[decision.selected_region]
    target_base = region_config["url"]

    # SSRF check — should always pass since decision engine uses configured regions
    if target_base not in settings.allowed_target_urls:
        logger.critical(f"[SSRF] Attempted forward to non-allowlisted URL: {target_base}")
        raise HTTPException(status_code=500, detail="Internal routing error")

    target_url = f"{target_base.rstrip('/')}/{path.lstrip('/')}"
    query = str(request.url.query)
    if query:
        target_url = f"{target_url}?{query}"

    # ── Step 4: Forward request ───────────────────────────────────────────────
    body = await request.body()
    upstream_headers = await _build_upstream_headers(request)
    success = False
    upstream_status = None
    error_msg = None

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            upstream_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=upstream_headers,
                content=body,
            )
        upstream_status = upstream_resp.status_code
        success = upstream_resp.status_code < 500

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Step 5: Build response ─────────────────────────────────────────
        response_headers = {
            "X-Eco-Router-Region": decision.selected_region,
            "X-Carbon-Intensity": str(decision.selected_intensity),
            "X-Request-Id": request_id,
            "X-Carbon-Data-Source": decision.carbon_data_source,
        }
        # Forward safe upstream response headers
        for k, v in upstream_resp.headers.items():
            if k.lower() not in HOP_BY_HOP_HEADERS | {"content-encoding"}:
                response_headers[k] = v

        # ── Step 6: Log event ─────────────────────────────────────────────
        _emit_routing_event(
            request_id, request, decision, latency_ms,
            success, upstream_status, error_msg, carbon_readings
        )

        # ── Step 7: Persist decision (async, fire-and-forget) ─────────────
        app_state.pending_decisions.append({
            "decision": decision,
            "method": request.method,
            "path": f"/{path}",
            "latency_ms": latency_ms,
            "success": success,
            "upstream_status_code": upstream_status,
            "error_message": None,
        })

        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers=response_headers,
            media_type=upstream_resp.headers.get("content-type", "application/json"),
        )

    except httpx.TimeoutException:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        error_msg = "upstream_timeout"
        _emit_routing_event(
            request_id, request, decision, latency_ms,
            False, None, error_msg, carbon_readings
        )
        raise HTTPException(
            status_code=504,
            detail={
                "error": "upstream_timeout",
                "region": decision.selected_region,
                "request_id": request_id,
            },
        )
    except httpx.RequestError as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        error_msg = f"upstream_error: {type(e).__name__}"
        _emit_routing_event(
            request_id, request, decision, latency_ms,
            False, None, error_msg, carbon_readings
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "region": decision.selected_region,
                "request_id": request_id,
            },
        )


def _emit_routing_event(
    request_id: str,
    request: Request,
    decision: RoutingDecision,
    latency_ms: float,
    success: bool,
    upstream_status: int | None,
    error: str | None,
    carbon_readings: dict,
) -> None:
    """Emit the structured log event for this routing decision."""
    emit_routing_event({
        "request_id": request_id,
        "method": request.method,
        "path": str(request.url.path),
        "candidates": decision.candidates,
        "selected_region": decision.selected_region,
        "selected_carbon_intensity": decision.selected_intensity,
        "decision": "lowest_carbon_available_region",
        "carbon_data_source": decision.carbon_data_source,
        "target_status": "available",
        "success": success,
        "latency_ms": latency_ms,
        "estimated_savings_gco2e": decision.estimated_savings_gco2e,
        "upstream_status_code": upstream_status,
        "error": error,
    })


def _emit_failure_event(
    request_id: str,
    request: Request,
    error: str,
    start_time: float,
    carbon_readings: dict,
) -> None:
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    emit_routing_event({
        "request_id": request_id,
        "method": request.method,
        "path": str(request.url.path),
        "candidates": {r: cr.intensity for r, cr in carbon_readings.items()},
        "selected_region": None,
        "selected_carbon_intensity": None,
        "decision": "no_available_region",
        "carbon_data_source": "n/a",
        "target_status": "all_unavailable",
        "success": False,
        "latency_ms": latency_ms,
        "error": error,
    })
