"""
forecast_tools.py -- Forecast data tools for AI agents.
Calls eco_router.forecast (Phase C statistical forecasting).
"""
from __future__ import annotations
from typing import Any


async def get_forecast_data(region: str | None = None, app_state: Any = None) -> dict:
    """
    Get carbon forecast data. Requires app_state for current readings.
    Returns clearly-labelled forecast or insufficient-data state.
    """
    try:
        if app_state is None:
            return {
                "available": False,
                "message": "app_state required for forecast tool.",
                "region": region,
                "data_type": "FORECAST_ERROR",
            }
        from eco_router.forecast import forecast_region, forecast_all_regions
        if region:
            data = await forecast_region(region, app_state)
        else:
            data = await forecast_all_regions(app_state)

        has_data = (
            data.get("status") == "ok"
            if region
            else any(v.get("status") == "ok" for v in data.get("regions", {}).values())
        )
        return {
            "available": has_data,
            "data": data,
            "region": region,
            "data_type": "FORECAST",
        }
    except Exception as e:
        return {
            "available": False,
            "message": f"Forecast error: {e}",
            "region": region,
            "data_type": "FORECAST_ERROR",
        }
