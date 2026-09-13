"""
Carbon-Aware Decision Engine — the core of Eco-Router.

This module implements the deterministic routing algorithm that selects
the lowest-carbon AVAILABLE region for each incoming workload.

Algorithm (must remain deterministic and explainable — no LLM involvement):
  1. Load configured regions
  2. Check region health → remove UNAVAILABLE
  3. Retrieve carbon readings → remove invalid/None
  4. Check data freshness → mark stale, use with warning
  5. Compare carbon intensities
  6. Select minimum-intensity region
  7. Break ties lexicographically (documented)
  8. Compute estimated carbon savings (ESTIMATED label)
  9. Return RoutingDecision

Tie-breaking rule:
  When two regions share identical carbon intensity, the tie is broken by
  lexicographic ordering of the region name ("eu-north-1" < "us-east-1").
  This is deterministic, auditable, and documented.

Carbon savings methodology:
  baseline     = max(candidate intensities)
  saved_per_kwh = baseline - selected_intensity
  estimated_g  = saved_per_kwh × ENERGY_PER_REQUEST_KWH (configurable)
  Label: ESTIMATED — not a measured real-world emission reduction.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from eco_router.schemas import CarbonReading, RoutingDecision
from eco_router.config import settings


class NoAvailableRegionError(Exception):
    """Raised when no region passes availability + carbon data checks."""
    pass


class DecisionEngine:
    """
    Stateless decision engine — called with current state on each request.
    No mutable state. Thread-safe and async-safe.
    """

    def make_decision(
        self,
        carbon_readings: dict[str, CarbonReading],
        health_status: dict[str, str],
        request_id: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Core routing decision.

        Args:
            carbon_readings: Current carbon reading per region
            health_status:   Current health status per region (available/unavailable/degraded)
            request_id:      Optional request UUID (generated if not provided)

        Returns:
            RoutingDecision with selected region, intensities, reason, savings

        Raises:
            NoAvailableRegionError: when no eligible region exists
        """
        req_id = request_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        all_regions = list(settings.regions.keys())

        unavailable_regions: list[str] = []
        invalid_data_regions: list[str] = []
        candidates: dict[str, float] = {}

        # ── Step 1: Filter by availability ────────────────────────────────────
        for region in all_regions:
            status = health_status.get(region, "unknown")
            if status != "available":
                unavailable_regions.append(region)
                logger.debug(
                    f"[DecisionEngine] {region} excluded: status={status}"
                )
                continue

            # ── Step 2: Filter by carbon data validity ─────────────────────
            reading = carbon_readings.get(region)
            if reading is None:
                invalid_data_regions.append(region)
                logger.warning(
                    f"[DecisionEngine] {region} excluded: no carbon reading"
                )
                continue

            if reading.intensity is None or reading.intensity < 0:
                invalid_data_regions.append(region)
                logger.warning(
                    f"[DecisionEngine] {region} excluded: invalid intensity "
                    f"({reading.intensity})"
                )
                continue

            # Stale data: still usable but flagged
            if reading.is_stale:
                logger.warning(
                    f"[DecisionEngine] {region} has STALE carbon data — "
                    f"using with caution (source={reading.source})"
                )

            candidates[region] = reading.intensity

        # ── Step 3: Guard — no candidates ─────────────────────────────────────
        if not candidates:
            msg = (
                f"No eligible regions available. "
                f"Unavailable: {unavailable_regions}, "
                f"Invalid data: {invalid_data_regions}"
            )
            logger.error(f"[DecisionEngine] {msg}")
            raise NoAvailableRegionError(msg)

        # ── Step 4: Select minimum-intensity region ────────────────────────────
        # Tie-breaking: lexicographic on region name (deterministic, documented)
        selected_region = min(candidates, key=lambda r: (candidates[r], r))
        selected_intensity = candidates[selected_region]

        # ── Step 5: Determine data source label ───────────────────────────────
        selected_reading = carbon_readings[selected_region]
        carbon_data_source = selected_reading.source
        if selected_reading.is_stale:
            carbon_data_source = "stale"

        # ── Step 6: Carbon savings estimation (ESTIMATED) ─────────────────────
        baseline_intensity = max(candidates.values()) if len(candidates) > 1 else None
        estimated_savings: Optional[float] = None
        if baseline_intensity is not None and baseline_intensity > selected_intensity:
            avoided_per_kwh = baseline_intensity - selected_intensity
            estimated_savings = round(
                avoided_per_kwh * settings.energy_per_request_kwh, 8
            )

        # ── Step 7: Build reason string ───────────────────────────────────────
        reason_parts = [
            f"Lowest valid carbon intensity ({selected_intensity} gCO₂e/kWh) "
            f"among {len(candidates)} available eligible region(s)."
        ]
        if unavailable_regions:
            reason_parts.append(
                f"Excluded (unavailable): {', '.join(unavailable_regions)}."
            )
        if invalid_data_regions:
            reason_parts.append(
                f"Excluded (no valid data): {', '.join(invalid_data_regions)}."
            )
        if len(candidates) == 1 and candidates:
            reason_parts = [
                f"Only one available region with valid carbon data: "
                f"{selected_region} ({selected_intensity} gCO₂e/kWh)."
            ]
        reason = " ".join(reason_parts)

        decision = RoutingDecision(
            request_id=req_id,
            selected_region=selected_region,
            selected_intensity=selected_intensity,
            candidates=dict(sorted(candidates.items())),
            unavailable_regions=unavailable_regions,
            invalid_data_regions=invalid_data_regions,
            reason=reason,
            carbon_data_source=carbon_data_source,
            timestamp=now,
            baseline_intensity=baseline_intensity,
            estimated_savings_gco2e=estimated_savings,
            savings_label="ESTIMATED — not a measured real-world emission reduction",
        )

        logger.info(
            f"[DecisionEngine] Decision: {selected_region} "
            f"({selected_intensity} gCO₂e/kWh) "
            f"| candidates={candidates} "
            f"| savings~{estimated_savings} gCO₂e (ESTIMATED)"
        )
        return decision


# Shared singleton
decision_engine = DecisionEngine()
