"""
test_forecast.py -- Tests for Phase C carbon intensity forecasting.

Validates:
  - Exponential smoothing algorithm
  - Trend estimation
  - Forecast step generation
  - Confidence calculation
  - Insufficient data handling
  - All output correctly labelled FORECAST/PREDICTED
  - Routing engine completely unaffected by forecasting
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from eco_router.forecast import (
    exponential_smooth,
    estimate_trend,
    forecast_steps,
    compute_confidence,
    trend_label,
    MIN_READINGS,
    ALPHA,
)
from eco_router.decision_engine import DecisionEngine
from eco_router.schemas import CarbonReading


# ── Exponential Smoothing ─────────────────────────────────────────────────────

class TestExponentialSmoothing:
    def test_empty_returns_empty(self):
        assert exponential_smooth([]) == []

    def test_single_value_unchanged(self):
        result = exponential_smooth([100.0])
        assert result == [100.0]

    def test_constant_series_stays_constant(self):
        values = [70.0] * 10
        smoothed = exponential_smooth(values)
        assert all(abs(v - 70.0) < 0.01 for v in smoothed)

    def test_decreasing_series_smoothed(self):
        values = [340, 330, 320, 300, 290]
        smoothed = exponential_smooth(values)
        # Last value should be lower than first
        assert smoothed[-1] < smoothed[0]
        # All values should be positive
        assert all(v > 0 for v in smoothed)

    def test_increasing_series_smoothed(self):
        values = [70, 80, 90, 100, 110]
        smoothed = exponential_smooth(values)
        assert smoothed[-1] > smoothed[0]

    def test_smoothing_dampens_spikes(self):
        # Single spike should be damped
        values = [100.0] * 5 + [500.0] + [100.0] * 5
        smoothed = exponential_smooth(values)
        # The spike should not propagate fully
        assert max(smoothed) < 500.0

    def test_alpha_respected(self):
        # Alpha=1.0 means no smoothing (raw values)
        values = [100.0, 200.0, 300.0]
        smoothed = exponential_smooth(values, alpha=1.0)
        assert smoothed == values

    def test_alpha_zero_means_flat(self):
        # Alpha=0.0 means always return first value
        values = [100.0, 200.0, 300.0]
        smoothed = exponential_smooth(values, alpha=0.0)
        assert all(v == 100.0 for v in smoothed)


# ── Trend Estimation ──────────────────────────────────────────────────────────

class TestTrendEstimation:
    def test_flat_series_zero_trend(self):
        assert estimate_trend([100.0, 100.0, 100.0]) == pytest.approx(0.0)

    def test_decreasing_series_negative_trend(self):
        trend = estimate_trend([340.0, 310.0, 290.0, 270.0])
        assert trend < 0

    def test_increasing_series_positive_trend(self):
        trend = estimate_trend([70.0, 90.0, 110.0, 130.0])
        assert trend > 0

    def test_single_value_zero_trend(self):
        assert estimate_trend([100.0]) == pytest.approx(0.0)


# ── Trend Labels ─────────────────────────────────────────────────────────────

class TestTrendLabel:
    def test_negative_trend_is_decreasing(self):
        assert trend_label(-5.0) == "decreasing"

    def test_positive_trend_is_increasing(self):
        assert trend_label(5.0) == "increasing"

    def test_near_zero_trend_is_stable(self):
        assert trend_label(0.5) == "stable"
        assert trend_label(-0.5) == "stable"


# ── Forecast Steps ────────────────────────────────────────────────────────────

class TestForecastSteps:
    def make_steps(self, last=100.0, trend=0.0, steps=6):
        now = datetime.now(timezone.utc)
        return forecast_steps(last, trend, steps, now)

    def test_returns_correct_count(self):
        steps = self.make_steps(steps=6)
        assert len(steps) == 6

    def test_step_numbers_sequential(self):
        steps = self.make_steps(steps=4)
        assert [s["step"] for s in steps] == [1, 2, 3, 4]

    def test_all_labelled_forecast(self):
        steps = self.make_steps()
        assert all(s["label"] == "FORECAST" for s in steps)

    def test_all_have_note(self):
        steps = self.make_steps()
        assert all("PREDICTED" in s["note"] for s in steps)

    def test_values_clamped_positive(self):
        # Even with extreme negative trend, intensity >= 0
        steps = self.make_steps(last=10.0, trend=-100.0, steps=3)
        assert all(s["predicted_intensity"] >= 0 for s in steps)

    def test_values_clamped_upper(self):
        # Even with extreme positive trend, intensity <= 1500
        steps = self.make_steps(last=1400.0, trend=500.0, steps=3)
        assert all(s["predicted_intensity"] <= 1500.0 for s in steps)

    def test_zero_trend_stays_near_constant(self):
        steps = self.make_steps(last=70.0, trend=0.0, steps=6)
        # With zero trend all predictions should stay near 70
        assert all(abs(s["predicted_intensity"] - 70.0) < 5 for s in steps)

    def test_timestamps_present(self):
        steps = self.make_steps()
        assert all("timestamp" in s for s in steps)


# ── Confidence ────────────────────────────────────────────────────────────────

class TestConfidence:
    def test_min_readings_gives_low_confidence(self):
        c = compute_confidence(MIN_READINGS, is_stale=False)
        assert 0.4 < c < 0.7

    def test_more_readings_higher_confidence(self):
        c_low = compute_confidence(MIN_READINGS, is_stale=False)
        c_high = compute_confidence(MIN_READINGS + 10, is_stale=False)
        assert c_high > c_low

    def test_stale_reduces_confidence(self):
        c_fresh = compute_confidence(10, is_stale=False)
        c_stale = compute_confidence(10, is_stale=True)
        assert c_stale < c_fresh

    def test_confidence_bounded(self):
        c = compute_confidence(1000, is_stale=False)
        assert 0.0 <= c <= 1.0


# ── Routing Engine Independence ───────────────────────────────────────────────

class TestRoutingEngineUnaffectedByForecast:
    """Verify forecasting cannot affect routing decisions."""

    def make_readings(self):
        return {
            "us-east-1": CarbonReading(
                region="us-east-1", intensity=340, unit="gCO2e/kWh",
                timestamp=datetime.now(timezone.utc), source="mock", is_stale=False,
            ),
            "eu-north-1": CarbonReading(
                region="eu-north-1", intensity=70, unit="gCO2e/kWh",
                timestamp=datetime.now(timezone.utc), source="mock", is_stale=False,
            ),
            "ap-south-1": CarbonReading(
                region="ap-south-1", intensity=180, unit="gCO2e/kWh",
                timestamp=datetime.now(timezone.utc), source="mock", is_stale=False,
            ),
        }

    def test_engine_unaffected_by_smoothing(self):
        """Calling smoothing functions does not alter the routing decision."""
        engine = DecisionEngine()
        carbon = self.make_readings()
        health = {"us-east-1": "available", "eu-north-1": "available", "ap-south-1": "available"}

        d_before = engine.make_decision(carbon, health)

        # Run forecast math on the same values
        intensities = [r.intensity for r in carbon.values()]
        smoothed = exponential_smooth(intensities)
        trend = estimate_trend(smoothed)
        now = datetime.now(timezone.utc)
        _ = forecast_steps(smoothed[-1], trend, 6, now)

        d_after = engine.make_decision(carbon, health)

        assert d_before.selected_region == d_after.selected_region
        assert d_before.selected_intensity == d_after.selected_intensity

    def test_forecast_result_never_has_routing_authority(self):
        """Forecast output cannot be passed to decision engine as routing input."""
        now = datetime.now(timezone.utc)
        steps = forecast_steps(70.0, -1.0, 3, now)
        # Forecast steps have no 'selected_region' field
        for step in steps:
            assert "selected_region" not in step
            assert "route_to" not in step
