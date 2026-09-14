"""Unit tests for Carbon Providers."""
from __future__ import annotations
import pytest
from datetime import datetime, timezone

from eco_router.providers.mock import MockCarbonProvider
from eco_router.providers.electricity_maps import ElectricityMapsProvider
from eco_router.providers.base import CarbonDataUnavailableError


class TestMockProvider:
    def setup_method(self):
        self.provider = MockCarbonProvider()
        self.provider.clear_all_overrides()

    @pytest.mark.asyncio
    async def test_returns_reading_for_all_regions(self):
        for region in ["us-east-1", "eu-north-1", "ap-south-1"]:
            reading = await self.provider.get_intensity(region)
            assert reading.region == region
            assert reading.intensity > 0
            assert reading.source == "mock"
            assert not reading.is_stale

    @pytest.mark.asyncio
    async def test_default_eu_lowest(self):
        readings = await self.provider.get_all_intensities(
            ["us-east-1", "eu-north-1", "ap-south-1"]
        )
        intensities = {r: v.intensity for r, v in readings.items()}
        assert intensities["eu-north-1"] < intensities["us-east-1"]
        assert intensities["eu-north-1"] < intensities["ap-south-1"]

    @pytest.mark.asyncio
    async def test_override_changes_value(self):
        self.provider.set_override("eu-north-1", 500.0)
        reading = await self.provider.get_intensity("eu-north-1")
        assert reading.intensity == 500.0

    @pytest.mark.asyncio
    async def test_clear_override_restores_default(self):
        default_reading = await self.provider.get_intensity("eu-north-1")
        default_val = default_reading.intensity
        self.provider.set_override("eu-north-1", 999.0)
        self.provider.clear_override("eu-north-1")
        restored = await self.provider.get_intensity("eu-north-1")
        assert restored.intensity == default_val

    @pytest.mark.asyncio
    async def test_timestamp_is_recent(self):
        reading = await self.provider.get_intensity("us-east-1")
        now = datetime.now(timezone.utc)
        age = (now - reading.timestamp).total_seconds()
        assert age < 5  # Should be within 5 seconds

    @pytest.mark.asyncio
    async def test_unknown_region_returns_default(self):
        reading = await self.provider.get_intensity("unknown-region")
        assert reading.intensity == 200.0  # Default fallback

    def test_get_current_values_dict(self):
        vals = self.provider.get_current_values()
        assert "us-east-1" in vals
        assert "eu-north-1" in vals
        assert "ap-south-1" in vals


class TestElectricityMapsProvider:
    """Tests for ElectricityMaps — should gracefully fail without key."""

    @pytest.mark.asyncio
    async def test_no_key_raises_not_crashes(self):
        """Without API key, should raise CarbonDataUnavailableError, not crash."""
        # Provider with no key
        import os
        original = os.environ.get("ELECTRICITY_MAPS_API_KEY", "")
        os.environ["ELECTRICITY_MAPS_API_KEY"] = ""
        try:
            from eco_router.providers.electricity_maps import ElectricityMapsProvider
            p = ElectricityMapsProvider()
            # is_configured should be False
            assert not p.is_configured
            with pytest.raises(CarbonDataUnavailableError):
                await p.get_intensity("eu-north-1")
        finally:
            if original:
                os.environ["ELECTRICITY_MAPS_API_KEY"] = original

    def test_provider_name(self):
        p = ElectricityMapsProvider()
        assert p.provider_name == "electricity_maps"
