"""
FastAPI application — Eco-Router entry point.

Startup sequence:
  1. Configure logging
  2. Initialize database
  3. Perform initial carbon + health data fetch
  4. Start background workers (carbon updater, health checker)
  5. Mount static files (dashboard)
  6. Include API routers

Shutdown sequence:
  1. Cancel background worker tasks
  2. Flush pending DB writes
  3. Close DB engine
"""
from __future__ import annotations
import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from eco_router import __version__
from eco_router.carbon_cache import carbon_updater_worker, refresh_all_carbon
from eco_router.config import settings
from eco_router.database import init_db, AsyncSessionLocal
from eco_router.decision_engine import decision_engine, NoAvailableRegionError
from eco_router.health import health_check_worker, run_health_checks
from eco_router.logging_config import configure_logging
from eco_router.providers.mock import mock_provider
from eco_router.repository import save_routing_decision
from eco_router.schemas import (
    CarbonReading,
    CarbonRegionInfo,
    CarbonResponse,
    DecisionResponse,
    MetricsResponse,
    RegionHealthStatus,
    RouterHealthResponse,
)

# ── Application State ─────────────────────────────────────────────────────────

class AppState:
    """Shared in-memory state accessed by all request handlers."""
    def __init__(self) -> None:
        self.carbon_readings: dict[str, CarbonReading] = {}
        self.health_status: dict[str, str] = {
            r: "unknown" for r in settings.regions
        }
        self.health_details: dict[str, RegionHealthStatus] = {}
        self.pending_decisions: list[dict] = []   # fire-and-forget DB writes
        self.start_time: float = time.time()

_app_state = AppState()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown orchestration."""
    configure_logging(settings.app_env)
    logger.info(
        f"[Eco-Router] v{__version__} starting "
        f"[env={settings.app_env}, provider={settings.carbon_provider}]"
    )

    # Initialise database
    await init_db()
    logger.info("[Startup] Database initialised")

    # Initial data fetch — uses fast 3s timeout per region so lifespan
    # doesn't block for up to 10s per unreachable region on cold start.
    await run_health_checks(_app_state, startup_probe=True)
    await refresh_all_carbon(_app_state)
    logger.info("[Startup] Initial health + carbon data loaded")


    # Start background workers
    carbon_task = asyncio.create_task(
        carbon_updater_worker(_app_state), name="carbon_updater"
    )
    health_task = asyncio.create_task(
        health_check_worker(_app_state), name="health_checker"
    )
    db_task = asyncio.create_task(
        _db_flush_worker(_app_state), name="db_flush"
    )

    logger.info("[Startup] Background workers started")
    logger.info(f"[Eco-Router] Ready at http://{settings.host}:{settings.port}")

    yield  # Application runs here

    # Shutdown
    logger.info("[Shutdown] Cancelling background workers...")
    for task in (carbon_task, health_task, db_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("[Shutdown] Eco-Router stopped cleanly")


async def _db_flush_worker(app_state: AppState) -> None:
    """
    Flushes pending routing decisions to SQLite.
    Runs every 2 seconds — decouples DB writes from request latency.
    """
    while True:
        try:
            await asyncio.sleep(2)
            if not app_state.pending_decisions:
                continue
            batch = app_state.pending_decisions.copy()
            app_state.pending_decisions.clear()
            async with AsyncSessionLocal() as db:
                for item in batch:
                    try:
                        await save_routing_decision(db, **item)
                    except Exception as e:
                        logger.error(f"[DBFlush] Failed to save decision: {e}")
                await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[DBFlush] Worker error: {e}")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Eco-Router",
    description=(
        "Carbon-Aware Intelligent API Load Balancer. "
        "Routes workloads to the lowest-carbon available region."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store state on app for access in routers
app.state.eco = _app_state

from eco_router.auth import router as auth_router
app.include_router(auth_router)

from eco_router.ai import router as ai_router  # noqa: E402
app.include_router(ai_router)


# ── Orchestrator Routes ───────────────────────────────────────────────────────

@app.post("/ai/ask", tags=["Eco Intelligence"])
async def ai_ask(request: Request):
    """
    Ask Eco-Router a natural-language question.

    The AI Orchestrator:
    1. Classifies intent (deterministically — no LLM for classification)
    2. Calls the appropriate agent (routing_analyst, carbon_analyst,
       forecast_analyst, infrastructure_advisor, sustainability_advisor)
    3. Gathers real telemetry via tools
    4. Synthesizes a grounded answer with Gemini (or demo mode)
    5. Returns structured response with agent, tools, data sources, confidence

    AI NEVER controls routing. The deterministic engine remains authoritative.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    question = str(body.get("question", "")).strip()[:512]
    if not question:
        return JSONResponse(
            status_code=400,
            content={"error": "question field is required and must be non-empty"},
        )

    from eco_router.ai.orchestrator import ask as orchestrator_ask
    state: AppState = request.app.state.eco
    result = await orchestrator_ask(question, state)
    # Instrument: record AI request metrics (Phase F)
    record_ai_request(intent=result.intent, mode=result.mode)
    return {
        "question": result.question,
        "intent": result.intent,
        "agent_used": result.agent_used,
        "tools_used": result.tools_used,
        "data_sources": result.data_sources,
        "answer": result.answer,
        "confidence": result.confidence,
        "mode": result.mode,
        "timestamp": result.timestamp,
        "disclaimer": result.disclaimer,
    }


@app.get("/ai/knowledge/search", tags=["Eco Intelligence"])
async def ai_knowledge_search(q: str = "", top_k: int = 3):
    """
    Search the Eco-Router sustainability knowledge base using BM25 retrieval.
    Returns retrieved knowledge chunks — no Gemini call, pure retrieval.
    Phase D: BM25 over knowledge/ markdown files.
    """
    q = q.strip()[:256]
    if not q:
        return JSONResponse(
            status_code=400, content={"error": "q parameter is required"}
        )
    from eco_router.rag import retrieve, get_index_status
    chunks = await retrieve(q, top_k=min(top_k, 5))
    status = get_index_status()
    return {
        "query": q,
        "sources": [
            {
                "source": c.source,
                "chunk_id": c.chunk_id,
                "score": c.score,
                "content": c.content,
            }
            for c in chunks
        ],
        "count": len(chunks),
        "index_chunks": status["chunk_count"],
        "retrieval_algorithm": "BM25",
        "data_type": "KNOWLEDGE_RETRIEVAL",
    }


@app.post("/ai/knowledge/reload", tags=["Eco Intelligence"])
async def ai_knowledge_reload():
    """
    Reload the knowledge base index from the knowledge/ directory.
    Use after adding new .md files to knowledge/ without restarting the server.
    """
    from eco_router.rag import reload_index
    status = reload_index()
    return {"message": "Knowledge index reloaded", "status": status}


@app.get("/ai/knowledge/status", tags=["Eco Intelligence"])
async def ai_knowledge_status():
    """Return the current knowledge index status."""
    from eco_router.rag import get_index_status
    return get_index_status()


@app.get("/cloud/regions", tags=["Infrastructure"])
async def cloud_regions():
    """
    Return safe metadata for all configured cloud regions.

    Phase H: uses pluggable CloudRegionProvider (mock by default, AWS when configured).
    SECURITY: Never returns credentials, internal URLs, or target endpoints.
    Set REGION_PROVIDER=aws + AWS credentials to activate AWS provider.
    """
    from eco_router.cloud import get_provider
    provider = get_provider()
    return provider.to_api_response()


@app.get("/cloud/regions/{region_id}", tags=["Infrastructure"])
async def cloud_region_detail(region_id: str):
    """Return safe metadata for a single cloud region."""
    from eco_router.cloud import get_provider
    provider = get_provider()
    region = provider.get_region(region_id)
    if not region:
        return JSONResponse(
            status_code=404,
            content={"error": f"Region '{region_id}' not found", "available_regions": [r.id for r in provider.list_regions()]},
        )
    return region.to_api_dict()


# ── Carbon Forecasting Routes (Phase C) ──────────────────────────────────────

@app.get("/forecast", tags=["Forecasting"])
async def forecast_all(request: Request, window_hours: int = 6, horizon_steps: int = 6):
    """
    Statistical carbon intensity forecast for all regions.

    Uses exponential smoothing on historical readings from the DB.
    All values are clearly labelled FORECAST / PREDICTED.

    Returns InsufficientData if < 3 readings exist for a region.
    """
    from eco_router.forecast import forecast_all_regions
    state: AppState = request.app.state.eco
    return await forecast_all_regions(state, window_hours=window_hours, horizon_steps=horizon_steps)


@app.get("/forecast/{region}", tags=["Forecasting"])
async def forecast_one(region: str, request: Request, window_hours: int = 6, horizon_steps: int = 6):
    """
    Statistical carbon intensity forecast for a single region.

    Values are PREDICTED — not real-time grid measurements.
    """
    from eco_router.forecast import forecast_region
    state: AppState = request.app.state.eco
    result = await forecast_region(region, state, window_hours=window_hours, horizon_steps=horizon_steps)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


# ── Observability Endpoints (Phase F) ────────────────────────────────────────

from eco_router.prom_metrics import (
    generate_metrics_output, get_metrics_status,
    update_carbon_gauges, update_health_gauges, update_uptime,
    record_ai_request,
)


@app.get("/metrics", tags=["Observability"])
async def prometheus_metrics(request: Request):
    """
    Prometheus-format metrics endpoint.

    Exposes:
      eco_router_requests_total          — proxied requests (region, status)
      eco_router_routing_decisions_total — decisions (region, carbon_source)
      eco_router_carbon_intensity_gauge  — live intensity per region
      eco_router_request_latency_seconds — request latency histogram
      eco_router_carbon_savings_gco2e_total — cumulative ESTIMATED savings
      eco_router_region_health_gauge     — health (1=available, 0.5=degraded, 0=down)
      eco_router_uptime_seconds          — application uptime
      eco_router_ai_requests_total       — AI ask requests (intent, mode)

    Optional bearer token protection: set PROMETHEUS_AUTH_TOKEN in env.
    """
    state: AppState = request.app.state.eco
    update_carbon_gauges(state.carbon_readings)
    update_health_gauges(state.health_status)
    update_uptime(state.start_time)
    body, content_type = generate_metrics_output()
    from fastapi.responses import Response
    return Response(content=body, media_type=content_type)


@app.get("/observability/status", tags=["Observability"])
async def observability_status(request: Request):
    """Full observability stack status including Prometheus availability."""
    from eco_router.rag import get_index_status
    state: AppState = request.app.state.eco
    uptime = round(time.time() - state.start_time, 1)
    metrics_status = get_metrics_status()
    rag_status = get_index_status()
    return {
        "uptime_seconds": uptime,
        "ai_mode": "AI_ANALYSIS" if settings.gemini_api_key else "AI_DEMO_MODE",
        "carbon_provider": settings.carbon_provider,
        "database": "sqlite" if "sqlite" in settings.database_url else "postgresql",
        "log_format": "structured (loguru)",
        "prometheus": metrics_status,
        "grafana": {
            "enabled": False,
            "note": "Phase G will add Grafana dashboard + docker-compose service",
        },
        "knowledge_base": {
            "chunk_count": rag_status["chunk_count"],
            "source_files": rag_status["source_files"],
            "retrieval_algorithm": rag_status["retrieval_algorithm"],
        },
        "forecast": {
            "algorithm": "exponential_smoothing",
            "requires_history": True,
            "min_readings": 3,
        },
        "phases_active": {
            "A_audit": True,
            "B_multi_agent": True,
            "C_forecasting": True,
            "D_rag": rag_status["chunk_count"] > 0,
            "E_alembic": False,
            "F_prometheus": metrics_status["prometheus_available"],
            "G_grafana": False,
            "H_aws": False,
            "I_kubernetes": False,
            "J_voice": False,
        },
    }


# ── Static Files (Dashboard) ──────────────────────────────────────────────────
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ── Core Routes ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def dashboard():
    """Serve the Eco-Router dashboard."""
    index = os.path.join(_static_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return JSONResponse({"message": "Eco-Router is running. Visit /docs for API."})


@app.get("/login", include_in_schema=False)
async def login_page():
    """Serve the login page."""
    page = os.path.join(_static_dir, "login.html")
    if os.path.exists(page):
        return FileResponse(page)
    return JSONResponse({"message": "Login page not found."})


@app.get("/register", include_in_schema=False)
async def register_page():
    """Serve the register page."""
    page = os.path.join(_static_dir, "register.html")
    if os.path.exists(page):
        return FileResponse(page)
    return JSONResponse({"message": "Register page not found."})


@app.get("/health", response_model=RouterHealthResponse, tags=["System"])
async def health(request: Request):
    """Eco-Router system health check."""
    state: AppState = request.app.state.eco
    uptime = time.time() - state.start_time
    # Find the most recent carbon reading timestamp
    last_update = None
    for reading in state.carbon_readings.values():
        ts = reading.timestamp.isoformat()
        if last_update is None or ts > last_update:
            last_update = ts
    return RouterHealthResponse(
        status="healthy",
        version=__version__,
        carbon_provider=settings.carbon_provider,
        regions=dict(state.health_status),
        database="sqlite",
        uptime_seconds=round(uptime, 1),
        last_carbon_update=last_update,
    )


@app.get("/carbon", response_model=CarbonResponse, tags=["Carbon"])
async def carbon(request: Request):
    """Current carbon intensity for all regions."""
    state: AppState = request.app.state.eco
    region_infos = []
    for region, cfg in settings.regions.items():
        reading = state.carbon_readings.get(region)
        if reading:
            region_infos.append(CarbonRegionInfo(
                region=region,
                name=cfg["name"],
                carbon_intensity=reading.intensity,
                unit=reading.unit,
                source=reading.source,
                is_stale=reading.is_stale,
                timestamp=reading.timestamp,
            ))
    return CarbonResponse(
        regions=region_infos,
        timestamp=datetime.now(timezone.utc),
        provider=settings.carbon_provider,
    )


@app.get("/decision", response_model=DecisionResponse, tags=["Carbon"])
async def decision(request: Request):
    """Current routing decision (preview — no workload forwarded)."""
    state: AppState = request.app.state.eco
    try:
        d = decision_engine.make_decision(
            carbon_readings=dict(state.carbon_readings),
            health_status=dict(state.health_status),
        )
        alternatives = {k: v for k, v in d.candidates.items() if k != d.selected_region}
        return DecisionResponse(
            selected_region=d.selected_region,
            carbon_intensity=d.selected_intensity,
            alternatives=alternatives,
            unavailable_regions=d.unavailable_regions,
            reason=d.reason,
            timestamp=d.timestamp,
            carbon_data_source=d.carbon_data_source,
            estimated_savings_gco2e=d.estimated_savings_gco2e,
        )
    except NoAvailableRegionError as e:
        return JSONResponse(
            status_code=503,
            content={"error": "no_available_region", "detail": str(e)},
        )


@app.get("/metrics", tags=["Metrics"])
async def metrics():
    """Routing metrics and carbon savings summary."""
    from eco_router.repository import get_routing_metrics
    async with AsyncSessionLocal() as db:
        data = await get_routing_metrics(db)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["savings_label"] = "ESTIMATED — not a measured emission reduction"
    return data


@app.get("/history", tags=["Metrics"])
async def history(limit: int = 20):
    """Recent routing decisions."""
    from eco_router.repository import get_recent_decisions
    import json as _json
    async with AsyncSessionLocal() as db:
        records = await get_recent_decisions(db, limit=limit)
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "method": r.method,
            "path": r.path,
            "selected_region": r.selected_region,
            "selected_intensity": r.selected_intensity,
            "carbon_data_source": r.carbon_data_source,
            "reason": r.reason,
            "latency_ms": r.latency_ms,
            "success": r.success,
            "estimated_savings_gco2e": r.estimated_savings_gco2e,
            "candidates": _json.loads(r.candidates_json) if r.candidates_json else {},
        }
        for r in records
    ]


# ── Demo / Simulation Control API ─────────────────────────────────────────────

@app.post("/demo/carbon", tags=["Demo"])
async def set_demo_carbon(
    region: str,
    intensity: float,
    request: Request,
):
    """
    Set a mock carbon intensity override for demo/simulation purposes.
    Only works when CARBON_PROVIDER=mock.
    Changes take effect immediately for routing decisions.
    """
    if region not in settings.regions:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown region: {region}. Valid: {list(settings.regions.keys())}"},
        )
    if intensity < 0:
        return JSONResponse(status_code=400, content={"error": "intensity must be >= 0"})

    from eco_router.providers.mock import mock_provider
    from eco_router.schemas import CarbonReading
    mock_provider.set_override(region, intensity)

    # Update app state immediately
    state: AppState = request.app.state.eco
    state.carbon_readings[region] = CarbonReading(
        region=region,
        intensity=intensity,
        unit="gCO2e/kWh",
        timestamp=datetime.now(timezone.utc),
        source="mock",
        is_stale=False,
    )
    return {
        "message": f"Carbon override set: {region} = {intensity} gCO₂e/kWh",
        "current_values": mock_provider.get_current_values(),
        "note": "SIMULATED data — not real grid measurements",
    }


@app.post("/demo/health", tags=["Demo"])
async def set_demo_health(
    region: str,
    status: str,
    request: Request,
):
    """
    Override region health status for failover demonstration.
    status: available | unavailable | degraded
    """
    if region not in settings.regions:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown region: {region}"},
        )
    if status not in ("available", "unavailable", "degraded"):
        return JSONResponse(
            status_code=400,
            content={"error": "status must be: available | unavailable | degraded"},
        )
    state: AppState = request.app.state.eco
    state.health_status[region] = status
    logger.info(f"[Demo] Health override: {region} → {status}")
    return {
        "message": f"Health override: {region} = {status}",
        "current_health": dict(state.health_status),
    }


@app.get("/demo/state", tags=["Demo"])
async def demo_state(request: Request):
    """Return current simulation state (carbon values + health status)."""
    state: AppState = request.app.state.eco
    return {
        "carbon_values": {
            r: state.carbon_readings[r].intensity
            for r in settings.regions if r in state.carbon_readings
        },
        "health_status": dict(state.health_status),
        "carbon_source": settings.carbon_provider,
        "note": "SIMULATED data — not real grid measurements",
    }


# ── AI Insight Endpoint ───────────────────────────────────────────────────────

def _rule_based_insight(ctx: dict) -> str:
    """
    Generate a plain-language explanation of the routing decision
    without any external API. Always works, zero dependencies.
    """
    sel = ctx.get("selected_region", "the selected region")
    intensity = ctx.get("carbon_intensity", 0)
    alternatives: dict = ctx.get("alternatives", {})
    unavailable: list = ctx.get("unavailable_regions", [])
    source = ctx.get("carbon_data_source", "mock")

    source_note = {
        "mock": "using simulated data",
        "cached": "using recently cached data",
        "stale": "using older cached data (flagged stale)",
        "electricity_maps": "using live Electricity Maps data",
        "live": "using live carbon data",
    }.get(source, f"using {source} data")

    lines = [
        f"{sel.upper()} was selected because its current grid carbon intensity "
        f"({intensity:.0f} gCO\u2082e/kWh) is the lowest among all eligible regions "
        f"({source_note}).",
    ]

    if alternatives:
        sorted_alts = sorted(alternatives.items(), key=lambda x: x[1])
        compared = "; ".join(f"{r.upper()} at {v:.0f}" for r, v in sorted_alts)
        lines.append(
            f"Compared alternatives: {compared} gCO\u2082e/kWh — all higher than {sel.upper()}."
        )

    if unavailable:
        lines.append(
            f"Excluded (unavailable): {', '.join(r.upper() for r in unavailable)}."
        )

    lines.append(
        "Note: carbon intensity reflects grid conditions — not a guarantee of renewable energy use."
    )
    return " ".join(lines)


async def _gemini_insight(ctx: dict, api_key: str) -> str:
    """
    Use Google Gemini to generate a natural-language explanation.
    Runs the synchronous Gemini call in the default thread executor.
    The AI explains only — it does NOT make routing decisions.
    """
    def _sync_call() -> str:
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=api_key)

            sel        = ctx.get("selected_region", "unknown")
            intensity  = ctx.get("carbon_intensity", 0)
            alternatives = ctx.get("alternatives", {})
            reason     = ctx.get("reason", "")
            source     = ctx.get("carbon_data_source", "mock")

            alt_lines = "\n".join(
                f"  - {r}: {v:.0f} gCO\u2082e/kWh" for r, v in alternatives.items()
            )

            prompt = (
                "You are an AI assistant for Eco-Router, a carbon-aware intelligent load balancer.\n"
                "Your ONLY role is to EXPLAIN routing decisions in plain language. "
                "You do NOT make routing decisions — the deterministic engine does.\n"
                "Keep your response to 3 sentences maximum. Be accurate and avoid overstatements.\n"
                "Do not claim the selected region uses renewable energy unless the data proves it.\n\n"
                f"Current routing decision:\n"
                f"  Selected region: {sel}\n"
                f"  Carbon intensity: {intensity:.0f} gCO\u2082e/kWh\n"
                f"  Data source: {source}\n"
                f"  Engine reason: {reason}\n"
                f"  Other eligible regions:\n{alt_lines}\n\n"
                "Explain why this region was selected in clear, honest language."
            )

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text.strip()
        except Exception as exc:
            logger.warning(f"[AI] Gemini call failed: {exc} — falling back to rule-based")
            return _rule_based_insight(ctx)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_call)


@app.post("/ai/insight", tags=["AI"])
async def ai_insight(request: Request):
    """
    Generate an AI-powered (or rule-based) explanation of the current routing decision.

    IMPORTANT:
    - AI DOES NOT make routing decisions.
    - The deterministic Decision Engine remains authoritative.
    - If GEMINI_API_KEY is not configured, rule-based explanation is returned.
    - The API key is NEVER exposed in the response or frontend.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    ctx = body.get("context", {})
    if not ctx:
        # Auto-populate from current decision if no context provided
        state: AppState = request.app.state.eco
        try:
            d = decision_engine.make_decision(
                carbon_readings=dict(state.carbon_readings),
                health_status=dict(state.health_status),
            )
            ctx = {
                "selected_region": d.selected_region,
                "carbon_intensity": d.selected_intensity,
                "alternatives": {k: v for k, v in d.candidates.items() if k != d.selected_region},
                "unavailable_regions": d.unavailable_regions,
                "reason": d.reason,
                "carbon_data_source": d.carbon_data_source,
            }
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"error": "no_available_region", "detail": str(e)},
            )

    if settings.gemini_api_key:
        insight = await _gemini_insight(ctx, settings.gemini_api_key)
        source = "gemini"
    else:
        insight = _rule_based_insight(ctx)
        source = "rule-based"

    return {
        "insight": insight,
        "source": source,
        "ai_controlled_routing": False,
        "disclaimer": (
            "AI-generated explanation only. "
            "Routing decisions are made exclusively by the deterministic Decision Engine."
        ),
    }


# ── Proxy Route ───────────────────────────────────────────────────────────────

from eco_router.proxy import forward_request   # noqa: E402


@app.api_route(
    "/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Proxy"],
    summary="Carbon-aware reverse proxy",
    description=(
        "Forwards the request to the lowest-carbon available region. "
        "Targets are determined by Eco-Router — clients cannot specify arbitrary URLs (SSRF protection)."
    ),
)
async def proxy(path: str, request: Request):
    """Carbon-aware reverse proxy endpoint — records Prometheus metrics."""
    import time as _time
    from eco_router.prom_metrics import record_request, record_decision, record_latency, record_savings
    state: AppState = request.app.state.eco

    # Capture pre-decision state for metrics
    try:
        pre_decision = decision_engine.make_decision(
            carbon_readings=dict(state.carbon_readings),
            health_status=dict(state.health_status),
        )
        _region = pre_decision.selected_region
        _source = pre_decision.carbon_data_source
        _savings = pre_decision.estimated_savings_gco2e
    except Exception:
        _region = "unknown"
        _source = "unknown"
        _savings = None

    t0 = _time.time()
    response = await forward_request(request, path, state)
    elapsed = _time.time() - t0

    _status = "success" if response.status_code < 500 else "error"
    record_request(region=_region, status=_status)
    record_decision(region=_region, carbon_source=_source)
    record_latency(region=_region, latency_seconds=elapsed)
    if _savings:
        record_savings(estimated_gco2e=_savings)

    return response

