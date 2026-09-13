"""
forecast.py -- Carbon intensity forecasting for Eco-Router.

PHASE C: Statistical forecasting. No ML libraries. No external APIs.

Algorithm:
  - Collects last N carbon readings from DB per region
  - Applies exponential smoothing (ETS-style)
  - Projects forward FORECAST_HORIZON_STEPS steps
  - Reports trend direction and confidence

Data labelling:
  - All predictions are clearly labelled: FORECAST / PREDICTED
  - NOT real-time grid measurements
  - NOT guaranteed

If insufficient history exists (< 3 readings):
  - Returns InsufficientData state rather than fabricating values

Endpoints (registered in main.py):
  GET /forecast           -> all regions
  GET /forecast/{region}  -> single region
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from eco_router.config import settings
from eco_router.database import AsyncSessionLocal
from eco_router.db_models import CarbonMeasurement

# ── Configuration ─────────────────────────────────────────────────────────────

ALPHA = 0.3                  # smoothing factor (0=flat, 1=reactive)
MIN_READINGS = 3             # minimum history points required
STEP_MINUTES = 60            # spacing between forecast steps (minutes)

# ── Exponential Smoothing ────────────────────────────────────────────────────

def exponential_smooth(values: list[float], alpha: float = ALPHA) -> list[float]:
    """
    Single exponential smoothing.
    smoothed[0] = values[0]
    smoothed[t] = alpha * values[t] + (1-alpha) * smoothed[t-1]
    """
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


def estimate_trend(smoothed: list[float]) -> float:
    """
    Simple linear trend: slope of first-vs-last smoothed values.
    Returns gCO2e/kWh per step (positive = rising, negative = falling).
    """
    if len(smoothed) < 2:
        return 0.0
    return (smoothed[-1] - smoothed[0]) / max(len(smoothed) - 1, 1)


def forecast_steps(
    last_smoothed: float,
    trend: float,
    steps: int,
    base_time: datetime,
) -> list[dict]:
    """
    Project forward using trend + mean reversion damping.
    Damping factor prevents unbounded extrapolation.
    """
    results = []
    damping = 0.85  # reduce trend impact per step
    current = last_smoothed
    current_trend = trend
    for i in range(1, steps + 1):
        current_trend *= damping
        current = current + current_trend
        # Clamp to physically plausible range
        current = max(0.0, min(current, 1500.0))
        results.append({
            "step": i,
            "timestamp": (base_time + timedelta(minutes=STEP_MINUTES * i)).isoformat(),
            "predicted_intensity": round(current, 1),
            "label": "FORECAST",
            "note": "PREDICTED — not a measured grid value",
        })
    return results


def compute_confidence(num_readings: int, is_stale: bool) -> float:
    """Confidence grows with more data, reduced if latest reading is stale."""
    base = min(0.95, 0.5 + (num_readings - MIN_READINGS) * 0.05)
    if is_stale:
        base *= 0.7
    return round(base, 2)


def trend_label(trend: float) -> str:
    if trend < -2:
        return "decreasing"
    elif trend > 2:
        return "increasing"
    return "stable"


# ── DB History Retrieval ──────────────────────────────────────────────────────

async def get_carbon_history(region: str, window_hours: int = 6) -> list[float]:
    """
    Fetch historical carbon intensity readings for a region from the DB.
    Returns list of intensities (oldest first).
    """
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CarbonMeasurement)
            .where(CarbonMeasurement.region == region)
            .where(CarbonMeasurement.timestamp >= since)
            .where(CarbonMeasurement.intensity >= 0)
            .order_by(CarbonMeasurement.timestamp)
            .limit(200)
        )
        records = result.scalars().all()
    return [r.intensity for r in records]


# ── Forecast for One Region ───────────────────────────────────────────────────

async def forecast_region(
    region: str,
    app_state: Any,
    window_hours: int = 6,
    horizon_steps: int = 6,
) -> dict:
    """
    Compute a forecast for a single region.
    Falls back to current reading if insufficient history.
    """
    if region not in settings.regions:
        return {"error": f"Unknown region: {region}"}

    history = await get_carbon_history(region, window_hours)
    current_reading = app_state.carbon_readings.get(region)
    current_intensity = current_reading.intensity if current_reading else None
    is_stale = current_reading.is_stale if current_reading else True
    source = current_reading.source if current_reading else "unknown"

    # Include the current live reading in history for better smoothing
    if current_intensity is not None:
        history.append(current_intensity)

    if len(history) < MIN_READINGS:
        return {
            "region": region,
            "name": settings.regions[region].get("name", region),
            "status": "insufficient_data",
            "message": (
                f"Only {len(history)} reading(s) available for {region}. "
                f"Need at least {MIN_READINGS}. "
                "Run the application for longer to accumulate history."
            ),
            "current_intensity": current_intensity,
            "model": "exponential_smoothing",
            "simulated": settings.carbon_provider == "mock",
            "data_label": "INSUFFICIENT_DATA",
        }

    smoothed = exponential_smooth(history)
    trend = estimate_trend(smoothed)
    confidence = compute_confidence(len(history), is_stale)

    now = datetime.now(timezone.utc)
    steps = forecast_steps(smoothed[-1], trend, horizon_steps, now)

    logger.debug(
        f"[Forecast] {region}: {len(history)} readings, "
        f"trend={trend:+.1f}, confidence={confidence}"
    )

    return {
        "region": region,
        "name": settings.regions[region].get("name", region),
        "status": "ok",
        "current_intensity": round(current_intensity, 1) if current_intensity is not None else None,
        "current_source": source,
        "is_stale": is_stale,
        "history_readings_used": len(history),
        "smoothed_current": round(smoothed[-1], 1),
        "trend_per_step": round(trend, 2),
        "trend": trend_label(trend),
        "forecast": steps,
        "confidence": confidence,
        "model": "exponential_smoothing",
        "alpha": ALPHA,
        "step_interval_minutes": STEP_MINUTES,
        "simulated": settings.carbon_provider == "mock",
        "data_label": "FORECAST",
        "disclaimer": (
            "Carbon intensity forecast uses statistical extrapolation of historical readings. "
            "PREDICTED values are NOT real-time grid measurements. "
            "Accuracy degrades with longer horizons."
        ),
    }


async def forecast_all_regions(app_state: Any, window_hours: int = 6, horizon_steps: int = 6) -> dict:
    """Compute forecasts for all configured regions."""
    import asyncio
    tasks = {
        region: forecast_region(region, app_state, window_hours, horizon_steps)
        for region in settings.regions
    }
    results = {}
    for region, coro in tasks.items():
        results[region] = await coro

    # Find the cleanest forecasted region (first step if available)
    cleanest_forecast = None
    cleanest_intensity = float("inf")
    for region, data in results.items():
        if data.get("status") == "ok" and data.get("forecast"):
            first_step = data["forecast"][0]["predicted_intensity"]
            if first_step < cleanest_intensity:
                cleanest_intensity = first_step
                cleanest_forecast = region

    return {
        "regions": results,
        "cleanest_forecast_region": cleanest_forecast,
        "cleanest_forecast_intensity": round(cleanest_intensity, 1) if cleanest_forecast else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "exponential_smoothing",
        "data_label": "FORECAST",
        "simulated": settings.carbon_provider == "mock",
        "disclaimer": (
            "All forecast values are PREDICTED via statistical extrapolation. "
            "Not real-time grid data. Not verified emissions data."
        ),
    }
