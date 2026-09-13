"""
Repository layer — all database read/write operations.
Abstracts SQLAlchemy from the rest of the application.
Designed for SQLite (dev) → PostgreSQL (production) migration.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from eco_router.db_models import (
    CarbonMeasurement,
    RegionHealthRecord,
    RoutingDecisionRecord,
)
from eco_router.schemas import CarbonReading, RegionHealthStatus, RoutingDecision


# ── Routing Decisions ─────────────────────────────────────────────────────────

async def save_routing_decision(
    db: AsyncSession,
    decision: RoutingDecision,
    method: str,
    path: str,
    latency_ms: float,
    success: bool,
    upstream_status_code: Optional[int] = None,
    error_message: Optional[str] = None,
) -> RoutingDecisionRecord:
    record = RoutingDecisionRecord(
        id=decision.request_id,
        timestamp=decision.timestamp,
        method=method,
        path=path,
        selected_region=decision.selected_region,
        selected_intensity=decision.selected_intensity,
        carbon_data_source=decision.carbon_data_source,
        reason=decision.reason,
        candidates_json=json.dumps(decision.candidates),
        unavailable_regions_json=json.dumps(decision.unavailable_regions),
        baseline_intensity=decision.baseline_intensity,
        estimated_savings_gco2e=decision.estimated_savings_gco2e,
        latency_ms=latency_ms,
        success=success,
        upstream_status_code=upstream_status_code,
        error_message=error_message,
    )
    db.add(record)
    await db.flush()
    return record


async def get_recent_decisions(
    db: AsyncSession,
    limit: int = 50,
) -> list[RoutingDecisionRecord]:
    result = await db.execute(
        select(RoutingDecisionRecord)
        .order_by(desc(RoutingDecisionRecord.timestamp))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_routing_metrics(db: AsyncSession) -> dict:
    """Aggregate metrics from stored decisions."""
    total = await db.scalar(select(func.count(RoutingDecisionRecord.id)))
    successes = await db.scalar(
        select(func.count(RoutingDecisionRecord.id)).where(
            RoutingDecisionRecord.success == True  # noqa: E712
        )
    )
    failures = (total or 0) - (successes or 0)

    # Requests by region
    region_rows = await db.execute(
        select(
            RoutingDecisionRecord.selected_region,
            func.count(RoutingDecisionRecord.id).label("cnt"),
        ).group_by(RoutingDecisionRecord.selected_region)
    )
    routing_by_region = {row.selected_region: row.cnt for row in region_rows}

    # Total estimated savings
    total_savings = await db.scalar(
        select(func.sum(RoutingDecisionRecord.estimated_savings_gco2e))
    )

    # Average carbon intensity of selected regions
    avg_intensity = await db.scalar(
        select(func.avg(RoutingDecisionRecord.selected_intensity))
    )

    return {
        "total_requests": total or 0,
        "successful_routes": successes or 0,
        "failed_routes": failures,
        "routing_by_region": routing_by_region,
        "estimated_total_savings_gco2e": round(total_savings or 0.0, 6),
        "avg_selected_intensity": round(avg_intensity or 0.0, 2),
    }


# ── Carbon Measurements ───────────────────────────────────────────────────────

async def save_carbon_measurement(
    db: AsyncSession,
    reading: CarbonReading,
) -> CarbonMeasurement:
    record = CarbonMeasurement(
        region=reading.region,
        intensity=reading.intensity,
        source=reading.source,
        timestamp=reading.timestamp,
        is_stale=reading.is_stale,
    )
    db.add(record)
    await db.flush()
    return record


async def get_recent_carbon(
    db: AsyncSession,
    region: str,
    limit: int = 10,
) -> list[CarbonMeasurement]:
    result = await db.execute(
        select(CarbonMeasurement)
        .where(CarbonMeasurement.region == region)
        .order_by(desc(CarbonMeasurement.timestamp))
        .limit(limit)
    )
    return list(result.scalars().all())


# ── Region Health ─────────────────────────────────────────────────────────────

async def save_health_record(
    db: AsyncSession,
    status: RegionHealthStatus,
) -> RegionHealthRecord:
    record = RegionHealthRecord(
        region=status.region,
        status=status.status,
        checked_at=status.checked_at,
        response_ms=status.response_ms,
    )
    db.add(record)
    await db.flush()
    return record


async def get_latest_health(db: AsyncSession) -> dict[str, str]:
    """Return the most recent health status per region."""
    subq = (
        select(
            RegionHealthRecord.region,
            func.max(RegionHealthRecord.checked_at).label("latest"),
        )
        .group_by(RegionHealthRecord.region)
        .subquery()
    )
    result = await db.execute(
        select(RegionHealthRecord).join(
            subq,
            (RegionHealthRecord.region == subq.c.region)
            & (RegionHealthRecord.checked_at == subq.c.latest),
        )
    )
    return {r.region: r.status for r in result.scalars().all()}
