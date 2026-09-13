"""
Electricity Maps Carbon Intensity Provider.

Official API documentation (verified): https://static.electricitymap.org/api/docs/index.html
API Version: v3
Base URL: https://api.electricitymap.org/v3

Authentication: "auth-token: {API_KEY}" request header
Endpoint used: GET /carbon-intensity/latest?zone={zone}

This provider is OPTIONAL. The application runs without it using MockCarbonProvider.

API KEY REQUIREMENTS:
  SERVICE:       Electricity Maps
  KEY NAME:      ELECTRICITY_MAPS_API_KEY
  WHERE:         https://api.electricitymap.org (free tier available)
  REQUIRED:      No — only when CARBON_PROVIDER=electricity_maps
  HOW USED:      Passed as "auth-token" header. Never logged. Never exposed to frontend.

Rate limits (free tier): ~10 requests/hour per zone
Data resolution: Near-real-time (typically 15-60 min lag)

Zone codes used:
  us-east-1  → US-MIDA-PJM  (PJM Interconnection — US Mid-Atlantic)
  eu-north-1 → SE            (Sweden — high renewables)
  ap-south-1 → IN-SO         (India South)
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger

from eco_router.providers.base import CarbonIntensityProvider, CarbonDataUnavailableError
from eco_router.schemas import CarbonReading
from eco_router.config import settings

# Electricity Maps zone codes for our simulated regions
ZONE_MAP: dict[str, str] = {
    "us-east-1":  "US-MIDA-PJM",
    "eu-north-1": "SE",
    "ap-south-1": "IN-SO",
}

_BASE_URL = "https://api.electricitymap.org/v3"
_TIMEOUT = 8.0  # seconds


class ElectricityMapsProvider(CarbonIntensityProvider):
    """
    Live carbon intensity from Electricity Maps API v3.
    Falls back gracefully when the API is unavailable.
    REQUIRES: ELECTRICITY_MAPS_API_KEY environment variable.
    """

    def __init__(self) -> None:
        self._api_key = settings.electricity_maps_api_key
        if not self._api_key:
            logger.warning(
                "[ElectricityMaps] No API key configured. "
                "Set ELECTRICITY_MAPS_API_KEY in .env to enable live data. "
                "Using MockCarbonProvider as fallback."
            )

    @property
    def provider_name(self) -> str:
        return "electricity_maps"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def get_intensity(self, region: str) -> CarbonReading:
        if not self.is_configured:
            raise CarbonDataUnavailableError(
                region, "ELECTRICITY_MAPS_API_KEY not configured"
            )

        zone = ZONE_MAP.get(region)
        if not zone:
            raise CarbonDataUnavailableError(
                region, f"No Electricity Maps zone mapping for region: {region}"
            )

        url = f"{_BASE_URL}/carbon-intensity/latest"
        # NOTE: API key is sent in a header — NEVER in the URL or logs
        headers = {"auth-token": self._api_key}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(
                    url, params={"zone": zone}, headers=headers
                )
                response.raise_for_status()
                data = response.json()

            intensity = float(data["carbonIntensity"])
            # Parse the datetime from the API response
            dt_str = data.get("datetime", "")
            try:
                timestamp = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

            logger.info(
                f"[ElectricityMaps] {region} ({zone}) → {intensity} gCO₂e/kWh"
            )
            return CarbonReading(
                region=region,
                intensity=intensity,
                unit="gCO2e/kWh",
                timestamp=timestamp,
                source="electricity_maps",
                is_stale=False,
            )

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"[ElectricityMaps] HTTP {e.response.status_code} for {region}/{zone}"
            )
            raise CarbonDataUnavailableError(
                region, f"HTTP {e.response.status_code}"
            )
        except httpx.TimeoutException:
            logger.warning(f"[ElectricityMaps] Timeout fetching {region}/{zone}")
            raise CarbonDataUnavailableError(region, "Request timed out")
        except Exception as e:
            logger.warning(f"[ElectricityMaps] Error fetching {region}: {e}")
            raise CarbonDataUnavailableError(region, str(e))

    async def get_all_intensities(
        self, regions: list[str]
    ) -> dict[str, CarbonReading]:
        """Fetch all regions concurrently."""
        results: dict[str, CarbonReading] = {}
        tasks = {region: self.get_intensity(region) for region in regions}
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for region, result in zip(tasks.keys(), responses):
            if isinstance(result, CarbonReading):
                results[region] = result
            else:
                logger.warning(
                    f"[ElectricityMaps] Failed to get {region}: {result}"
                )
        return results
