"""
history_tools.py -- Routing history retrieval for AI agents.
Reads from DB only. Never modifies state.
"""
from __future__ import annotations
from eco_router.database import AsyncSessionLocal
from eco_router.repository import get_recent_decisions, get_routing_metrics
import json as _json


async def get_routing_history(limit: int = 20) -> dict:
    """Fetch recent routing decisions from DB for AI analysis."""
    limit = min(limit, 50)
    async with AsyncSessionLocal() as db:
        records = await get_recent_decisions(db, limit=limit)
    decisions = [
        {
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
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
    return {
        "decisions": decisions,
        "count": len(decisions),
        "data_type": "ROUTING_HISTORY",
    }


async def get_routing_summary() -> dict:
    """Aggregate routing metrics for AI analysis."""
    async with AsyncSessionLocal() as db:
        metrics = await get_routing_metrics(db)
    return {
        "metrics": metrics,
        "data_type": "ROUTING_METRICS",
        "savings_label": "ESTIMATED -- not a measured emission reduction",
    }


def analyze_region_distribution(decisions: list) -> dict:
    """Count how often each region was selected. Pure computation, no I/O."""
    counts: dict[str, int] = {}
    for d in decisions:
        r = d.get("selected_region")
        if r:
            counts[r] = counts.get(r, 0) + 1
    total = sum(counts.values())
    distribution = {
        k: {"count": v, "pct": round(v / total * 100, 1) if total else 0}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    }
    return {"distribution": distribution, "total_decisions": total}
