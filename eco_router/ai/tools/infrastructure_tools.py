"""
infrastructure_tools.py -- Infrastructure state tools for AI agents.
"""
from __future__ import annotations
from typing import Any

from eco_router.config import settings
from eco_router.decision_engine import decision_engine


async def get_current_decision(app_state: Any) -> dict:
    """
    Run a non-forwarding routing decision using the deterministic engine.
    Returns the decision the engine WOULD make right now.
    AI uses this for explanation — it does NOT alter this result.
    """
    try:
        d = decision_engine.make_decision(
            carbon_readings=dict(app_state.carbon_readings),
            health_status=dict(app_state.health_status),
        )
        alternatives = {k: v for k, v in d.candidates.items() if k != d.selected_region}
        return {
            "selected_region": d.selected_region,
            "selected_intensity": d.selected_intensity,
            "alternatives": alternatives,
            "unavailable_regions": d.unavailable_regions,
            "reason": d.reason,
            "carbon_data_source": d.carbon_data_source,
            "estimated_savings_gco2e": d.estimated_savings_gco2e,
            "savings_label": d.savings_label,
            "timestamp": d.timestamp.isoformat(),
            "data_type": "ROUTING_DECISION",
            "ai_controlled": False,
        }
    except Exception as e:
        return {
            "error": str(e),
            "data_type": "ROUTING_DECISION",
            "ai_controlled": False,
        }


async def get_region_info() -> dict:
    """Return static region metadata (no secrets)."""
    regions = {}
    for region_id, cfg in settings.regions.items():
        regions[region_id] = {
            "name": cfg.get("name", region_id),
            "electricity_maps_zone": cfg.get("electricity_maps_zone"),
        }
    return {"regions": regions, "data_type": "REGION_METADATA"}
