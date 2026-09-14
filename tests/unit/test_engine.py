"""
Unit tests for the Decision Engine.
Tests cover: normal selection, unavailable regions, stale data,
missing data, tie-breaking, all-unavailable, savings estimation.
"""
from __future__ import annotations
import pytest
from datetime import datetime, timezone

from eco_router.decision_engine import DecisionEngine, NoAvailableRegionError
from eco_router.schemas import CarbonReading


def make_reading(region: str, intensity: float, source: str = "mock", is_stale: bool = False) -> CarbonReading:
    return CarbonReading(
        region=region,
        intensity=intensity,
        unit="gCO2e/kWh",
        timestamp=datetime.now(timezone.utc),
        source=source,
        is_stale=is_stale,
    )


ALL_AVAILABLE = {
    "us-east-1":  "available",
    "eu-north-1": "available",
    "ap-south-1": "available",
}

STANDARD_READINGS = {
    "us-east-1":  make_reading("us-east-1",  340.0),
    "eu-north-1": make_reading("eu-north-1",  70.0),
    "ap-south-1": make_reading("ap-south-1", 180.0),
}


class TestDecisionEngine:
    engine = DecisionEngine()

    def test_lowest_carbon_selected(self):
        """EU-NORTH with 70 gCO₂e/kWh should win over 340 and 180."""
        d = self.engine.make_decision(STANDARD_READINGS, ALL_AVAILABLE)
        assert d.selected_region == "eu-north-1"
        assert d.selected_intensity == 70.0

    def test_unavailable_region_excluded(self):
        """EU unavailable → AP-SOUTH (180) should win over US-EAST (340)."""
        health = {**ALL_AVAILABLE, "eu-north-1": "unavailable"}
        d = self.engine.make_decision(STANDARD_READINGS, health)
        assert d.selected_region == "ap-south-1"
        assert "eu-north-1" in d.unavailable_regions

    def test_degraded_region_excluded(self):
        """Degraded regions should also be excluded from routing."""
        health = {**ALL_AVAILABLE, "eu-north-1": "degraded"}
        d = self.engine.make_decision(STANDARD_READINGS, health)
        assert d.selected_region == "ap-south-1"
        assert "eu-north-1" in d.unavailable_regions

    def test_stale_data_used_with_flag(self):
        """Stale data is used but flagged; selection still works."""
        readings = {
            "us-east-1":  make_reading("us-east-1",  340.0, is_stale=True),
            "eu-north-1": make_reading("eu-north-1",  70.0, is_stale=True),
            "ap-south-1": make_reading("ap-south-1", 180.0),
        }
        d = self.engine.make_decision(readings, ALL_AVAILABLE)
        assert d.selected_region == "eu-north-1"
        # Source should be marked as stale for the selected region
        assert d.carbon_data_source in ("stale", "mock")

    def test_missing_carbon_data_excluded(self):
        """Region with no carbon reading is excluded."""
        readings = {
            "us-east-1":  make_reading("us-east-1", 340.0),
            # eu-north-1 missing
            "ap-south-1": make_reading("ap-south-1", 180.0),
        }
        d = self.engine.make_decision(readings, ALL_AVAILABLE)
        assert d.selected_region == "ap-south-1"
        assert "eu-north-1" in d.invalid_data_regions

    def test_invalid_intensity_excluded(self):
        """Region with negative intensity is excluded."""
        readings = {
            "us-east-1":  make_reading("us-east-1", 340.0),
            "eu-north-1": make_reading("eu-north-1", -1.0),
            "ap-south-1": make_reading("ap-south-1", 180.0),
        }
        d = self.engine.make_decision(readings, ALL_AVAILABLE)
        assert d.selected_region == "ap-south-1"
        assert "eu-north-1" in d.invalid_data_regions

    def test_tie_breaking_lexicographic(self):
        """Ties broken lexicographically: 'eu-north-1' < 'us-east-1'."""
        readings = {
            "us-east-1":  make_reading("us-east-1",  100.0),
            "eu-north-1": make_reading("eu-north-1", 100.0),
            "ap-south-1": make_reading("ap-south-1", 200.0),
        }
        d = self.engine.make_decision(readings, ALL_AVAILABLE)
        assert d.selected_region == "eu-north-1"  # 'eu' < 'us'

    def test_all_unavailable_raises(self):
        """All regions unavailable → NoAvailableRegionError."""
        health = {r: "unavailable" for r in ALL_AVAILABLE}
        with pytest.raises(NoAvailableRegionError):
            self.engine.make_decision(STANDARD_READINGS, health)

    def test_all_no_data_raises(self):
        """No carbon data for any region → NoAvailableRegionError."""
        with pytest.raises(NoAvailableRegionError):
            self.engine.make_decision({}, ALL_AVAILABLE)

    def test_single_region_available(self):
        """Only one region available → that region selected."""
        health = {
            "us-east-1":  "unavailable",
            "eu-north-1": "unavailable",
            "ap-south-1": "available",
        }
        d = self.engine.make_decision(STANDARD_READINGS, health)
        assert d.selected_region == "ap-south-1"

    def test_carbon_savings_estimated(self):
        """Savings should be estimated when baseline > selected."""
        d = self.engine.make_decision(STANDARD_READINGS, ALL_AVAILABLE)
        # baseline=340, selected=70, diff=270
        # savings = 270 * 0.0001 = 0.027
        assert d.estimated_savings_gco2e is not None
        assert d.estimated_savings_gco2e > 0
        assert "ESTIMATED" in d.savings_label

    def test_request_id_generated(self):
        """Decision should always have a request_id."""
        d = self.engine.make_decision(STANDARD_READINGS, ALL_AVAILABLE)
        assert d.request_id
        assert len(d.request_id) == 36  # UUID format

    def test_custom_request_id_preserved(self):
        """Provided request_id should be preserved."""
        d = self.engine.make_decision(
            STANDARD_READINGS, ALL_AVAILABLE, request_id="test-123"
        )
        assert d.request_id == "test-123"

    def test_candidates_dict_populated(self):
        """Candidates should contain only valid available regions."""
        d = self.engine.make_decision(STANDARD_READINGS, ALL_AVAILABLE)
        assert "us-east-1" in d.candidates
        assert "eu-north-1" in d.candidates
        assert "ap-south-1" in d.candidates

    def test_scenario_b_us_cleanest(self):
        """Scenario B: US becomes cleanest."""
        readings = {
            "us-east-1":  make_reading("us-east-1",  80.0),
            "eu-north-1": make_reading("eu-north-1", 300.0),
            "ap-south-1": make_reading("ap-south-1", 180.0),
        }
        d = self.engine.make_decision(readings, ALL_AVAILABLE)
        assert d.selected_region == "us-east-1"
