"""
Carbon cache and provider facade.
Maintains an in-memory cache of carbon readings with TTL.
Implements the fallback chain: Live → Cached → Mock

This module is the single point of access for carbon data.
No other module talks directly to providers.

Fallback chain:
  1. Try live provider (ElectricityMaps / CarbonAwareSDK)
  2. If fails → use cached reading (if not stale)
  3. If stale or absent → use mock provider
  Every reading returned includes source + is_stale flag.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from loguru import logger

from eco_router.config import settings
from eco_router.providers.base import CarbonDataUnavailableError
from eco_router.providers.mock import mock_provider
from eco_router.schemas import CarbonReading

if TYPE_CHECKING:
    from eco_router.providers.base import CarbonIntensityProvider


def _age_seconds(reading: CarbonReading) -> float:
    now = datetime.now(timezone.utc)
    ts = reading.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


class CarbonCache:
    """
    In-memory cache for carbon intensity readings.
    TTL is configurable via CARBON_CACHE_TTL (default 300s).
    """

    def __init__(self) -> None:
        self._cache: dict[str, CarbonReading] = {}

    def get(self, region: str) -> Optional[CarbonReading]:
        reading = self._cache.get(region)
        if reading is None:
            return None
        age = _age_seconds(reading)
        if age > settings.carbon_cache_ttl:
            # Mark stale but don't evict — may still be used as last resort
            stale = reading.model_copy(update={"is_stale": True})
            self._cache[region] = stale
            return stale
        return reading

    def set(self, region: str, reading: CarbonReading) -> None:
        self._cache[region] = reading

    def all_readings(self) -> dict[str, CarbonReading]:
        """Return a snapshot of all cached readings (may include stale)."""
        return dict(self._cache)

    def clear(self) -> None:
        self._cache.clear()


# Shared singleton cache
carbon_cache = CarbonCache()


def get_provider() -> "CarbonIntensityProvider":
    """Return the configured live provider, or mock if not configured."""
    provider_name = settings.carbon_provider.lower()
    if provider_name == "electricity_maps":
        from eco_router.providers.electricity_maps import ElectricityMapsProvider
        p = ElectricityMapsProvider()
        if p.is_configured:
            return p
        logger.warning(
            "[CarbonCache] ElectricityMaps not configured → falling back to mock"
        )
        return mock_provider
    elif provider_name == "carbon_aware_sdk":
        from eco_router.providers.carbon_aware import CarbonAwareSDKProvider
        p = CarbonAwareSDKProvider()
        if p.is_configured:
            return p
        logger.warning(
            "[CarbonCache] CarbonAwareSDK not configured → falling back to mock"
        )
        return mock_provider
    else:
        return mock_provider


async def fetch_carbon_reading(region: str) -> CarbonReading:
    """
    Fetch carbon intensity for one region using the full fallback chain.
    Never raises. Always returns a reading (source indicates provenance).
    """
    provider = get_provider()

    # ── Try live provider ────────────────────────────────────────────────────
    if provider.provider_name != "mock":
        try:
            reading = await provider.get_intensity(region)
            carbon_cache.set(region, reading)
            return reading
        except CarbonDataUnavailableError as e:
            logger.warning(
                f"[CarbonCache] Live provider failed for {region}: {e}. "
                "Trying cache..."
            )
        except Exception as e:
            logger.warning(
                f"[CarbonCache] Unexpected error from live provider for {region}: {e}"
            )

    # ── Try cache ────────────────────────────────────────────────────────────
    cached = carbon_cache.get(region)
    if cached is not None and not cached.is_stale:
        logger.debug(f"[CarbonCache] Serving cached reading for {region}")
        return cached.model_copy(update={"source": "cached"})

    if cached is not None and cached.is_stale:
        logger.warning(
            f"[CarbonCache] Only stale data available for {region} — "
            "falling back to mock"
        )

    # ── Fallback: mock ────────────────────────────────────────────────────────
    mock_reading = await mock_provider.get_intensity(region)
    logger.info(
        f"[CarbonCache] Using mock data for {region} "
        f"(source: {mock_reading.source})"
    )
    return mock_reading


async def refresh_all_carbon(app_state: "object") -> None:
    """
    Refresh carbon data for all configured regions.
    Updates both the in-memory cache and app_state.carbon_readings.
    Called by the background carbon updater worker.
    """
    regions = list(settings.regions.keys())
    readings = await asyncio.gather(
        *[fetch_carbon_reading(r) for r in regions],
        return_exceptions=True,
    )
    for region, result in zip(regions, readings):
        if isinstance(result, CarbonReading):
            carbon_cache.set(region, result)
            app_state.carbon_readings[region] = result
        else:
            logger.error(
                f"[CarbonCache] Failed to refresh {region}: {result}"
            )

    intensities = {
        r: app_state.carbon_readings[r].intensity
        for r in regions
        if r in app_state.carbon_readings
    }
    logger.info(f"[CarbonCache] Refreshed: {intensities}")


async def carbon_updater_worker(app_state: "object") -> None:
    """
    Background worker: refreshes carbon data on a configurable interval.
    Exceptions are caught — worker never kills the event loop.
    """
    logger.info(
        f"[CarbonWorker] Starting — interval={settings.carbon_update_interval}s"
    )
    while True:
        try:
            await refresh_all_carbon(app_state)
        except asyncio.CancelledError:
            logger.info("[CarbonWorker] Shutting down cleanly")
            break
        except Exception as e:
            logger.error(f"[CarbonWorker] Unexpected error (continuing): {e}")
        await asyncio.sleep(settings.carbon_update_interval)
