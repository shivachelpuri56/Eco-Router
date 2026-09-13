"""
Green Software Foundation Carbon Aware SDK Provider.

Official repository: https://github.com/Green-Software-Foundation/carbon-aware-sdk
Documentation: https://carbon-aware-sdk.greensoftware.foundation/

The SDK exposes a REST API that you self-host or connect to a hosted instance.
Typical base URL format: http://localhost:5073 (local) or a configured host.

This provider is OPTIONAL. The application runs fully without it.

API KEY REQUIREMENTS:
  SERVICE:       GSF Carbon Aware SDK
  KEY NAME:      CARBON_AWARE_SDK_URL
  WHERE:         Self-host from the GitHub repo above
  REQUIRED:      No — only when CARBON_PROVIDER=carbon_aware_sdk
  HOW USED:      Base URL for the SDK's REST API

NOTE: The Carbon Aware SDK location codes differ from Electricity Maps zones.
Mapping must be verified against your specific SDK version's supported locations.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone

import httpx
from loguru import logger

from eco_router.providers.base import CarbonIntensityProvider, CarbonDataUnavailableError
from eco_router.schemas import CarbonReading
from eco_router.config import settings

# Location codes for the Carbon Aware SDK
# These must be verified against your SDK's supported locations list.
LOCATION_MAP: dict[str, str] = {
    "us-east-1":  "eastus",
    "eu-north-1": "northeurope",
    "ap-south-1": "southindia",
}

_TIMEOUT = 8.0


class CarbonAwareSDKProvider(CarbonIntensityProvider):
    """
    Carbon intensity from Green Software Foundation's Carbon Aware SDK.
    Requires a running SDK instance and CARBON_AWARE_SDK_URL in .env.
    Falls back gracefully when unavailable.
    """

    def __init__(self) -> None:
        self._base_url = (settings.carbon_aware_sdk_url or "").rstrip("/")
        if not self._base_url:
            logger.warning(
                "[CarbonAwareSDK] No SDK URL configured. "
                "Set CARBON_AWARE_SDK_URL in .env to enable. "
                "Using MockCarbonProvider as fallback."
            )

    @property
    def provider_name(self) -> str:
        return "carbon_aware_sdk"

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url)

    async def get_intensity(self, region: str) -> CarbonReading:
        if not self.is_configured:
            raise CarbonDataUnavailableError(
                region, "CARBON_AWARE_SDK_URL not configured"
            )

        location = LOCATION_MAP.get(region)
        if not location:
            raise CarbonDataUnavailableError(
                region, f"No SDK location mapping for region: {region}"
            )

        url = f"{self._base_url}/emissions/bylocation"
        params = {"location": location}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            # The SDK returns a list; take the most recent entry
            if not data:
                raise CarbonDataUnavailableError(region, "Empty response from SDK")

            latest = data[0] if isinstance(data, list) else data
            intensity = float(latest.get("rating", latest.get("carbonIntensity", 0)))

            try:
                ts_str = latest.get("time", "")
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

            logger.info(
                f"[CarbonAwareSDK] {region} ({location}) → {intensity} gCO₂e/kWh"
            )
            return CarbonReading(
                region=region,
                intensity=intensity,
                unit="gCO2e/kWh",
                timestamp=timestamp,
                source="carbon_aware_sdk",
                is_stale=False,
            )

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"[CarbonAwareSDK] HTTP {e.response.status_code} for {region}"
            )
            raise CarbonDataUnavailableError(region, f"HTTP {e.response.status_code}")
        except httpx.TimeoutException:
            logger.warning(f"[CarbonAwareSDK] Timeout for {region}")
            raise CarbonDataUnavailableError(region, "Request timed out")
        except CarbonDataUnavailableError:
            raise
        except Exception as e:
            logger.warning(f"[CarbonAwareSDK] Error for {region}: {e}")
            raise CarbonDataUnavailableError(region, str(e))

    async def get_all_intensities(
        self, regions: list[str]
    ) -> dict[str, CarbonReading]:
        results: dict[str, CarbonReading] = {}
        tasks = {r: self.get_intensity(r) for r in regions}
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for region, result in zip(tasks.keys(), responses):
            if isinstance(result, CarbonReading):
                results[region] = result
            else:
                logger.warning(f"[CarbonAwareSDK] Failed for {region}: {result}")
        return results
