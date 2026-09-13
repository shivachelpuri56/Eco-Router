"""
Pydantic schemas (API request/response models) for Eco-Router.
Separate from SQLAlchemy ORM models in db_models.py.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Carbon Data ───────────────────────────────────────────────────────────────

class CarbonReading(BaseModel):
    """A single carbon intensity measurement for one region."""
    region: str
    intensity: float = Field(..., description="Grid carbon intensity (gCO₂e/kWh)")
    unit: str = "gCO2e/kWh"
    timestamp: datetime
    source: str  # "mock" | "electricity_maps" | "carbon_aware_sdk" | "cached"
    is_stale: bool = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "region": "eu-north-1",
                "intensity": 70.0,
                "unit": "gCO2e/kWh",
                "timestamp": "2026-09-01T15:30:00Z",
                "source": "mock",
                "is_stale": False,
            }
        }
    }


class CarbonRegionInfo(BaseModel):
    """Carbon info for one region, for the /carbon endpoint."""
    region: str
    name: str
    carbon_intensity: float
    unit: str = "gCO2e/kWh"
    source: str
    is_stale: bool
    timestamp: datetime


class CarbonResponse(BaseModel):
    """Response from GET /carbon."""
    regions: list[CarbonRegionInfo]
    timestamp: datetime
    provider: str
    note: str = (
        "Carbon intensity values drive routing decisions. "
        "Simulated data is clearly labelled source='mock'."
    )


# ── Routing Decision ──────────────────────────────────────────────────────────

class RoutingDecision(BaseModel):
    """The output of the Decision Engine for one routing event."""
    request_id: str
    selected_region: str
    selected_intensity: float
    candidates: dict[str, float]         # all regions with valid data
    unavailable_regions: list[str]       # skipped — health check failed
    invalid_data_regions: list[str]      # skipped — no/stale data
    reason: str
    carbon_data_source: str              # mock | live | cached | stale
    timestamp: datetime
    # ── Carbon Savings (ESTIMATED) ───────────────────────────────────────────
    baseline_intensity: Optional[float] = None
    estimated_savings_gco2e: Optional[float] = None
    savings_label: str = "ESTIMATED — not a verified emission reduction"


class DecisionResponse(BaseModel):
    """Response from GET /decision (preview — no request forwarded)."""
    selected_region: str
    carbon_intensity: float
    unit: str = "gCO2e/kWh"
    alternatives: dict[str, float]
    unavailable_regions: list[str]
    reason: str
    timestamp: datetime
    carbon_data_source: str
    estimated_savings_gco2e: Optional[float] = None
    savings_label: str = "ESTIMATED"


# ── Region Health ─────────────────────────────────────────────────────────────

class RegionHealthStatus(BaseModel):
    """Health status for one region."""
    region: str
    status: str   # "available" | "degraded" | "unavailable"
    checked_at: datetime
    response_ms: Optional[float] = None


class AllHealthResponse(BaseModel):
    """Response from GET /health/regions."""
    regions: dict[str, RegionHealthStatus]
    timestamp: datetime


# ── Metrics ───────────────────────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    """Response from GET /metrics."""
    total_requests: int
    successful_routes: int
    failed_routes: int
    routing_by_region: dict[str, int]
    estimated_total_savings_gco2e: float
    savings_label: str = "ESTIMATED"
    avg_selected_intensity: float
    last_updated: datetime


# ── Eco-Router Health ─────────────────────────────────────────────────────────

class RouterHealthResponse(BaseModel):
    """Response from GET /health."""
    status: str
    version: str
    carbon_provider: str
    regions: dict[str, str]   # region → health status
    database: str
    uptime_seconds: float
    last_carbon_update: Optional[str] = None  # ISO timestamp of most recent carbon refresh


# ── Proxy Routing Event Log ───────────────────────────────────────────────────

class RoutingEvent(BaseModel):
    """Structured log payload emitted for every proxied request."""
    request_id: str
    timestamp: datetime
    method: str
    path: str
    candidates: dict[str, float]
    selected_region: str
    selected_carbon_intensity: float
    decision: str
    carbon_data_source: str
    target_status: str
    success: bool
    latency_ms: float
    estimated_savings_gco2e: Optional[float] = None
    upstream_status_code: Optional[int] = None
    error: Optional[str] = None
