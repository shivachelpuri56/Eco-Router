"""
eco_router/cloud/provider.py — Abstract CloudRegionProvider interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from .models import CloudRegion


class CloudRegionProvider(ABC):
    """
    Abstract base for cloud region providers.

    Implementations must:
    - Return safe CloudRegion metadata only (no credentials/endpoints)
    - Gracefully handle missing credentials
    - Never expose internal URLs to API responses
    - Be thread-safe and async-compatible
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier: 'mock', 'aws', etc."""

    @abstractmethod
    def list_regions(self) -> list[CloudRegion]:
        """Return all known regions for this provider."""

    @abstractmethod
    def get_region(self, region_id: str) -> CloudRegion | None:
        """Return metadata for a specific region, or None if not found."""

    def is_available(self) -> bool:
        """
        Whether this provider is properly configured and usable.
        Override in providers that require credentials.
        """
        return True

    def to_api_response(self) -> dict:
        """Serialize all regions to a safe API response."""
        return {
            "provider": self.name,
            "regions": [r.to_api_dict() for r in self.list_regions()],
            "count": len(self.list_regions()),
            "note": (
                "Region metadata only. Target endpoints are server-side config. "
                "Clients cannot specify routing targets."
            ),
        }
