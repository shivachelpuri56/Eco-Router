"""
carbon_tools.py -- Carbon data retrieval tools for AI agents.

These functions READ from app state / config only.
They NEVER write state or control routing.
"""
from __future__ import annotations
from typing import Any

from eco_router.config import settings


async def get_carbon_snapshot(app_state: Any) -> dict:
    """Return current carbon intensity readings for all regions."""
    snapshot = {}
    for region in settings.regions:
        reading = app_state.carbon_readings.get(region)
        if reading:
            snapshot[region] = {
                "intensity": reading.intensity,
                "unit": reading.unit,
                "source": reading.source,
                "is_stale": reading.is_stale,
                "timestamp": reading.timestamp.isoformat(),
            }
        else:
            snapshot[region] = None
    return {
        "regions": snapshot,
        "provider": settings.carbon_provider,
        "data_type": "LIVE_APP_STATE",
    }


async def get_region_comparison(app_state: Any) -> dict:
    """Return sorted region carbon comparison — cleanest first."""
    readings = []
    for region in settings.regions:
        reading = app_state.carbon_readings.get(region)
        if reading and reading.intensity is not None:
            readings.append({
                "region": region,
                "name": settings.regions[region].get("name", region),
                "intensity": reading.intensity,
                "source": reading.source,
                "is_stale": reading.is_stale,
                "health": app_state.health_status.get(region, "unknown"),
            })
    readings.sort(key=lambda x: x["intensity"])
    if readings:
        cleanest = readings[0]["region"]
        dirtiest = readings[-1]["region"]
        spread = readings[-1]["intensity"] - readings[0]["intensity"]
    else:
        cleanest = dirtiest = None
        spread = 0.0
    return {
        "regions_sorted": readings,
        "cleanest_region": cleanest,
        "dirtiest_region": dirtiest,
        "carbon_spread_gco2e_kwh": round(spread, 2),
        "data_type": "CARBON_COMPARISON",
    }


async def get_carbon_provider_info() -> dict:
    """Return carbon provider configuration (no secrets exposed)."""
    return {
        "provider": settings.carbon_provider,
        "provider_is_live": settings.carbon_provider != "mock",
        "cache_ttl_seconds": settings.carbon_cache_ttl,
        "update_interval_seconds": settings.carbon_update_interval,
        "data_type": "PROVIDER_INFO",
    }
