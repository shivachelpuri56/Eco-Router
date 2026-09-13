"""
metrics_tools.py -- Live system metrics tools for AI agents.
"""
from __future__ import annotations
import time
from typing import Any

from eco_router.config import settings


async def get_system_metrics(app_state: Any) -> dict:
    """Return current system uptime, health status, and region availability."""
    uptime = round(time.time() - app_state.start_time, 1)
    available = sum(1 for s in app_state.health_status.values() if s == "available")
    total = len(settings.regions)
    return {
        "uptime_seconds": uptime,
        "regions_available": available,
        "regions_total": total,
        "availability_pct": round(available / total * 100, 1) if total else 0,
        "health_status": dict(app_state.health_status),
        "carbon_provider": settings.carbon_provider,
        "data_type": "SYSTEM_METRICS",
    }


async def get_health_summary(app_state: Any) -> dict:
    """Summarize region health for AI consumption."""
    summary = {}
    for region, status in app_state.health_status.items():
        summary[region] = {
            "status": status,
            "name": settings.regions.get(region, {}).get("name", region),
        }
    degraded = [r for r, s in app_state.health_status.items() if s == "degraded"]
    unavailable = [r for r, s in app_state.health_status.items() if s == "unavailable"]
    return {
        "regions": summary,
        "degraded": degraded,
        "unavailable": unavailable,
        "all_healthy": len(degraded) == 0 and len(unavailable) == 0,
        "data_type": "HEALTH_SUMMARY",
    }
