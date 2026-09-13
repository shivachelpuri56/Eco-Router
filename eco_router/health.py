"""
Health check system for Eco-Router.
Periodically pings each region's /health endpoint.
Regions that fail health checks are excluded from routing.

Health states:
  available   — responded with 2xx within timeout
  degraded    — responded but with high latency (future: >2x normal)
  unavailable — did not respond, 5xx, or timed out

The health state is stored in AppState.health_status and is the first
filter applied by the Decision Engine.
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from eco_router.config import settings
from eco_router.schemas import RegionHealthStatus

if TYPE_CHECKING:
    from eco_router.main import AppState


async def check_region_health(region: str, url: str, timeout: float | None = None) -> RegionHealthStatus:
    """
    Ping a region's /health endpoint and return its status.
    Never raises — always returns a status (unavailable on error).

    Args:
        timeout: Override the default request_timeout. Useful for startup
                 probes that need fast failure (e.g. 3s vs 10s).
    """
    health_url = url.rstrip("/") + "/health"
    start = time.perf_counter()
    _timeout = timeout if timeout is not None else settings.request_timeout

    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            response = await client.get(health_url)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if response.status_code < 300:
            status = "available"
        elif response.status_code < 500:
            status = "degraded"
        else:
            status = "unavailable"

        logger.debug(
            f"[HealthCheck] {region} → {status} "
            f"(HTTP {response.status_code}, {elapsed_ms:.1f}ms)"
        )
        return RegionHealthStatus(
            region=region,
            status=status,
            checked_at=datetime.now(timezone.utc),
            response_ms=round(elapsed_ms, 2),
        )

    except httpx.TimeoutException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(f"[HealthCheck] {region} → TIMEOUT ({elapsed_ms:.0f}ms)")
        return RegionHealthStatus(
            region=region,
            status="unavailable",
            checked_at=datetime.now(timezone.utc),
            response_ms=round(elapsed_ms, 2),
        )
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(f"[HealthCheck] {region} → ERROR: {e}")
        return RegionHealthStatus(
            region=region,
            status="unavailable",
            checked_at=datetime.now(timezone.utc),
            response_ms=None,
        )


async def run_health_checks(app_state: "AppState", startup_probe: bool = False) -> None:
    """
    Check all configured regions and update shared health state.
    Called by the background health-check worker and during lifespan startup.

    Args:
        startup_probe: If True, uses a short 3-second timeout per region so
                       the lifespan does not block for the full request_timeout
                       (default 10s) when region servers are still starting.
    """
    regions = settings.regions
    # Use a fast timeout during startup — regions may still be booting
    probe_timeout = 3.0 if startup_probe else None
    tasks = [
        check_region_health(region, cfg["url"], timeout=probe_timeout)
        for region, cfg in regions.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, RegionHealthStatus):
            app_state.health_status[result.region] = result.status
            app_state.health_details[result.region] = result
        else:
            logger.error(f"[HealthCheck] Unexpected error: {result}")

    statuses = {r: app_state.health_status.get(r, "unknown") for r in regions}
    logger.info(f"[HealthCheck] Status snapshot: {statuses}")


async def health_check_worker(app_state: "AppState") -> None:
    """
    Background worker that runs health checks on a configurable interval.
    Exceptions are caught so the worker never kills the event loop.
    """
    logger.info(
        f"[HealthWorker] Starting — interval={settings.health_check_interval}s"
    )
    while True:
        try:
            await run_health_checks(app_state)
        except asyncio.CancelledError:
            logger.info("[HealthWorker] Shutting down cleanly")
            break
        except Exception as e:
            logger.error(f"[HealthWorker] Unexpected error (continuing): {e}")
        await asyncio.sleep(settings.health_check_interval)
