"""
Mock Carbon Intensity Provider.

Returns configurable simulated carbon intensity values.
Used as the primary provider when no API key is configured,
and as the fallback when live providers fail.

All readings are clearly labelled:
  source="mock"
  simulated=True (in region responses)

Mock values are configurable via:
  - Environment variables (MOCK_CARBON_US_EAST_1 etc.)
  - Runtime API calls (for demo scenarios via /demo/carbon endpoint)

IMPORTANT: This data is SIMULATED. It does NOT reflect real grid conditions.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from loguru import logger
from eco_router.providers.base import CarbonIntensityProvider
from eco_router.schemas import CarbonReading
from eco_router.config import settings


class MockCarbonProvider(CarbonIntensityProvider):
    """
    Simulated carbon intensity provider for development and demonstration.

    Default values (gCO₂e/kWh) illustrate geographic carbon intensity variation:
      us-east-1:   340  (coal/gas-heavy US grid)
      eu-north-1:   70  (Nordic hydro/wind — very clean)
      ap-south-1:  180  (mixed Indian grid)

    These are ILLUSTRATIVE APPROXIMATIONS — not real-time measurements.
    Real grids vary significantly by hour and season.
    """

    # Runtime-overridable values (modified by demo/simulation controls)
    _overrides: dict[str, float] = {}

    @property
    def provider_name(self) -> str:
        return "mock"

    def _current_value(self, region: str) -> float:
        """Return runtime override if set, otherwise config/env default."""
        if region in self._overrides:
            return self._overrides[region]
        return settings.mock_carbon_values.get(region, 200.0)

    async def get_intensity(self, region: str) -> CarbonReading:
        """Return a simulated carbon reading. Never raises."""
        intensity = self._current_value(region)
        reading = CarbonReading(
            region=region,
            intensity=intensity,
            unit="gCO2e/kWh",
            timestamp=datetime.now(timezone.utc),
            source="mock",
            is_stale=False,
        )
        logger.debug(
            f"[MockProvider] {region} → {intensity} gCO₂e/kWh (simulated)"
        )
        return reading

    async def get_all_intensities(
        self, regions: list[str]
    ) -> dict[str, CarbonReading]:
        """Fetch all regions concurrently (instant for mock)."""
        readings = await asyncio.gather(
            *[self.get_intensity(r) for r in regions]
        )
        return {r.region: r for r in readings}

    # ── Runtime Control (for demo scenarios) ─────────────────────────────────

    def set_override(self, region: str, intensity: float) -> None:
        """
        Set a runtime carbon intensity override for a region.
        Used by the simulation control API to change values without
        modifying source code or restarting the server.
        """
        self._overrides[region] = intensity
        logger.info(
            f"[MockProvider] Override set: {region} = {intensity} gCO₂e/kWh"
        )

    def clear_override(self, region: str) -> None:
        """Remove a runtime override, reverting to env/config default."""
        self._overrides.pop(region, None)
        logger.info(f"[MockProvider] Override cleared: {region}")

    def clear_all_overrides(self) -> None:
        """Reset all overrides to env/config defaults."""
        self._overrides.clear()
        logger.info("[MockProvider] All overrides cleared")

    def get_current_values(self) -> dict[str, float]:
        """Return the effective carbon value for every known region."""
        return {
            region: self._current_value(region)
            for region in settings.regions.keys()
        }


# Shared singleton — one instance used by the whole application
mock_provider = MockCarbonProvider()
