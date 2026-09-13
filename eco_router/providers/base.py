"""
Abstract base class for all carbon intensity providers.
Every provider must implement get_intensity() and return a CarbonReading.

Provider chain (fallback order):
  1. Live provider (ElectricityMaps, CarbonAwareSDK)
  2. Cached reading (if within TTL)
  3. Mock provider (always available)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from eco_router.schemas import CarbonReading


class CarbonIntensityProvider(ABC):
    """
    Interface for carbon intensity data sources.
    All implementations must be async-safe.
    """

    @abstractmethod
    async def get_intensity(self, region: str) -> CarbonReading:
        """
        Retrieve the current carbon intensity for a region.

        Args:
            region: Region identifier e.g. "eu-north-1"

        Returns:
            CarbonReading with intensity (gCO₂e/kWh), timestamp, source, is_stale

        Raises:
            CarbonDataUnavailableError: when data cannot be fetched and no cache
        """
        ...

    @abstractmethod
    async def get_all_intensities(
        self, regions: list[str]
    ) -> dict[str, CarbonReading]:
        """
        Retrieve intensities for all given regions.
        Implementations should parallelise where possible.
        Returns a dict; missing regions may be absent (caller handles gaps).
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of this provider (logged with every reading)."""
        ...


class CarbonDataUnavailableError(Exception):
    """Raised when no carbon data can be obtained for a region."""
    def __init__(self, region: str, reason: str = ""):
        self.region = region
        super().__init__(f"Carbon data unavailable for {region}: {reason}")
