"""
eco_router/cloud/mock_provider.py — Mock cloud region provider.

Returns the three existing simulated regions (us-east-1, eu-north-1, ap-south-1).
No credentials required. Safe for demos and local development.
"""
from __future__ import annotations
from .models import CloudRegion
from .provider import CloudRegionProvider


# Simulated region metadata — mirrors eco_router/config.py DEFAULT_REGIONS
_MOCK_REGIONS: list[CloudRegion] = [
    CloudRegion(
        id="us-east-1",
        provider="mock",
        display_name="US East (N. Virginia)",
        latitude=37.43,
        longitude=-79.00,
        electricity_maps_zone="US-MIDA-PJM",
        available=True,
        metadata={
            "simulated": True,
            "grid_type": "mixed",
            "typical_intensity_gco2e_kwh": 340,
        },
    ),
    CloudRegion(
        id="eu-north-1",
        provider="mock",
        display_name="EU North (Stockholm)",
        latitude=59.33,
        longitude=18.07,
        electricity_maps_zone="SE",
        available=True,
        metadata={
            "simulated": True,
            "grid_type": "hydro_nuclear",
            "typical_intensity_gco2e_kwh": 70,
        },
    ),
    CloudRegion(
        id="ap-south-1",
        provider="mock",
        display_name="Asia Pacific (Mumbai)",
        latitude=19.08,
        longitude=72.88,
        electricity_maps_zone="IN-SO",
        available=True,
        metadata={
            "simulated": True,
            "grid_type": "coal_renewable_mix",
            "typical_intensity_gco2e_kwh": 180,
        },
    ),
]

_REGION_MAP: dict[str, CloudRegion] = {r.id: r for r in _MOCK_REGIONS}


class MockCloudRegionProvider(CloudRegionProvider):
    """
    Returns simulated cloud regions.
    Always available — requires no credentials.
    Used as the default provider and as fallback when AWS credentials are absent.
    """

    @property
    def name(self) -> str:
        return "mock"

    def list_regions(self) -> list[CloudRegion]:
        return list(_MOCK_REGIONS)

    def get_region(self, region_id: str) -> CloudRegion | None:
        return _REGION_MAP.get(region_id)

    def is_available(self) -> bool:
        return True
