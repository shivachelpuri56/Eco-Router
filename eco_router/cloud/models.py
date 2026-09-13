"""
eco_router/cloud/models.py — CloudRegion data model.

This is the safe metadata representation of a cloud region.
It NEVER includes credentials, internal endpoints, or secret values.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CloudRegion:
    """
    Safe, public-facing metadata for a cloud region.

    Fields:
        id            — unique region identifier (e.g. "us-east-1")
        provider      — provider name: "mock" | "aws" | "gcp" | "azure"
        display_name  — human-readable region name
        latitude      — approximate geographic latitude (for globe marker)
        longitude     — approximate geographic longitude
        electricity_maps_zone — zone code for carbon intensity lookups
        available     — whether the region is currently healthy
        metadata      — arbitrary additional provider-specific safe metadata

    NOT included (security):
        - credentials
        - API keys
        - internal URLs / endpoints (those stay in server-side config)
        - private network addresses
    """
    id: str
    provider: str
    display_name: str
    latitude: float
    longitude: float
    electricity_maps_zone: str = ""
    available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> dict:
        """Serialize to the safe API response format."""
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "electricity_maps_zone": self.electricity_maps_zone,
            "available": self.available,
            # metadata is allowed through only for non-sensitive keys
            "metadata": {
                k: v for k, v in self.metadata.items()
                if k not in {"endpoint", "url", "secret", "key", "token", "password"}
            },
        }
