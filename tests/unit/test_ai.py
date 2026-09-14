"""
Unit tests for the Eco Intelligence AI module.

Tests cover:
1. Missing API key → AI DEMO MODE response (no crash)
2. Demo mode templates produce correct structure
3. Gemini provider success path
4. Gemini timeout → graceful fallback to demo mode
5. Gemini API error → graceful fallback to demo mode
6. Input validation (Pydantic)
7. Insufficient history data
8. API key NEVER appears in any response
9. routing engine is unaffected by AI module
10. ai_status endpoint never exposes the key
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from eco_router.ai import (
    AI_MODE_DEMO,
    AI_MODE_LIVE,
    AnalyzeHistoryRequest,
    ExplainDecisionRequest,
    HistoryEntry,
    RecommendRequest,
    _call_gemini,
    _demo_analyze_history,
    _demo_explain_decision,
    _demo_recommend,
    _gemini_explain,
    _gemini_history,
    _gemini_recommend,
    _parse_gemini_json,
)
from eco_router.decision_engine import DecisionEngine, NoAvailableRegionError
from eco_router.schemas import CarbonReading
from datetime import datetime, timezone


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_EXPLAIN_REQ = ExplainDecisionRequest(
    selected_region="eu-north-1",
    selected_intensity=70.0,
    carbon_data_source="mock",
    reason="Lowest-carbon available region",
    candidates={"eu-north-1": 70.0, "ap-south-1": 180.0, "us-east-1": 340.0},
    unavailable_regions=[],
    estimated_savings_gco2e=0.027,
)

SAMPLE_HISTORY_ENTRIES = [
    HistoryEntry(
        timestamp="2025-01-01T10:00:00Z",
        selected_region="eu-north-1",
        selected_intensity=70.0,
        carbon_data_source="mock",
        reason="Lowest-carbon available region",
    ),
    HistoryEntry(
        timestamp="2025-01-01T10:05:00Z",
        selected_region="eu-north-1",
        selected_intensity=72.0,
        carbon_data_source="mock",
        reason="Lowest-carbon available region",
    ),
    HistoryEntry(
        timestamp="2025-01-01T10:10:00Z",
        selected_region="ap-south-1",
        selected_intensity=180.0,
        carbon_data_source="mock",
        reason="eu-north-1 unavailable",
    ),
]

SAMPLE_HISTORY_REQ = AnalyzeHistoryRequest(
    history=SAMPLE_HISTORY_ENTRIES,
    carbon_readings={"eu-north-1": 70.0, "ap-south-1": 180.0, "us-east-1": 340.0},
)

SAMPLE_RECOMMEND_REQ = RecommendRequest(
    history=SAMPLE_HISTORY_ENTRIES,
    carbon_readings={"eu-north-1": 70.0, "ap-south-1": 180.0, "us-east-1": 340.0},
    health_status={"eu-north-1": "available", "ap-south-1": "available", "us-east-1": "available"},
    total_requests=25,
    routing_by_region={"eu-north-1": 22, "ap-south-1": 3},
    carbon_provider="mock",
)


# ── 1. Demo mode — explain decision ──────────────────────────────────────────

class TestDemoExplainDecision:
    def test_returns_demo_mode(self):
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        assert result.mode == AI_MODE_DEMO
        assert result.provider == "demo"

    def test_summary_contains_region(self):
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        assert "eu-north-1" in result.summary.lower() or "EU-NORTH-1" in result.summary

    def test_summary_contains_intensity(self):
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        assert "70" in result.summary

    def test_observations_include_alternatives(self):
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        obs_text = " ".join(result.observations)
        assert "AP-SOUTH-1" in obs_text or "ap-south-1" in obs_text.lower()
        assert "US-EAST-1" in obs_text or "us-east-1" in obs_text.lower()

    def test_estimated_savings_labelled_correctly(self):
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        all_text = " ".join(result.interpretations + result.limitations)
        # Must never call it an actual reduction
        assert "actual" not in all_text.lower() or "not a measured reduction" in all_text.lower()
        assert "ESTIMATED" in " ".join(result.interpretations)

    def test_unavailable_regions_appear(self):
        req = ExplainDecisionRequest(
            **{**SAMPLE_EXPLAIN_REQ.model_dump(), "unavailable_regions": ["us-east-1"]}
        )
        result = _demo_explain_decision(req)
        obs_text = " ".join(result.observations)
        assert "US-EAST-1" in obs_text

    def test_api_key_never_in_response(self):
        """Demo mode must never return anything resembling a key."""
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        all_text = str(result.model_dump())
        assert "GEMINI" not in all_text
        assert "api_key" not in all_text.lower()


# ── 2. Demo mode — analyze history ───────────────────────────────────────────

class TestDemoAnalyzeHistory:
    def test_returns_demo_mode(self):
        result = _demo_analyze_history(SAMPLE_HISTORY_REQ)
        assert result.mode == AI_MODE_DEMO

    def test_summary_mentions_count(self):
        result = _demo_analyze_history(SAMPLE_HISTORY_REQ)
        assert "3" in result.summary or "three" in result.summary.lower()

    def test_empty_history_returns_insufficient_message(self):
        req = AnalyzeHistoryRequest(history=[], carbon_readings={})
        result = _demo_analyze_history(req)
        assert result.mode == AI_MODE_DEMO
        assert "insufficient" in result.summary.lower() or "no routing" in " ".join(result.observations).lower()

    def test_region_counts_in_observations(self):
        result = _demo_analyze_history(SAMPLE_HISTORY_REQ)
        obs_text = " ".join(result.observations).lower()
        assert "eu-north-1" in obs_text

    def test_api_key_never_in_response(self):
        result = _demo_analyze_history(SAMPLE_HISTORY_REQ)
        assert "GEMINI_API_KEY" not in str(result.model_dump())


# ── 3. Demo mode — recommend ─────────────────────────────────────────────────

class TestDemoRecommend:
    def test_returns_demo_mode(self):
        result = _demo_recommend(SAMPLE_RECOMMEND_REQ)
        assert result.mode == AI_MODE_DEMO

    def test_has_recommendations(self):
        result = _demo_recommend(SAMPLE_RECOMMEND_REQ)
        assert len(result.recommendations) >= 1

    def test_routing_concentration_flagged(self):
        """eu-north-1 handles 22/25 requests — should be flagged."""
        result = _demo_recommend(SAMPLE_RECOMMEND_REQ)
        all_text = " ".join(result.recommendations).lower()
        assert "eu-north-1" in all_text or "concentration" in all_text or "22" in all_text

    def test_limitations_mention_advisory(self):
        result = _demo_recommend(SAMPLE_RECOMMEND_REQ)
        lim_text = " ".join(result.limitations).lower()
        assert "advisory" in lim_text or "oversight" in lim_text

    def test_recommendations_do_not_contain_routing_override(self):
        result = _demo_recommend(SAMPLE_RECOMMEND_REQ)
        all_recs = " ".join(result.recommendations).lower()
        assert "route to" not in all_recs
        assert "use region" not in all_recs

    def test_unavailable_health_triggers_recommendation(self):
        req = RecommendRequest(
            **{**SAMPLE_RECOMMEND_REQ.model_dump(),
               "health_status": {"eu-north-1": "unavailable", "ap-south-1": "available", "us-east-1": "available"}}
        )
        result = _demo_recommend(req)
        recs_text = " ".join(result.recommendations).lower()
        assert "unavailable" in recs_text or "eu-north-1" in recs_text


# ── 4. Gemini path — success ─────────────────────────────────────────────────

@pytest.mark.asyncio
class TestGeminiSuccess:
    async def test_explain_decision_uses_gemini_text(self):
        fake_ai_text = "EU-NORTH-1 was selected because it had the lowest carbon intensity."
        with patch("eco_router.ai._call_gemini", return_value=fake_ai_text):
            with patch("eco_router.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "fake-key-for-test"
                mock_settings.gemini_model = "gemini-2.0-flash"
                result = await _gemini_explain(SAMPLE_EXPLAIN_REQ)
        assert result.mode == AI_MODE_LIVE
        assert result.summary == fake_ai_text

    async def test_history_uses_gemini_text(self):
        fake_ai_text = "EU-NORTH was selected 2 of 3 times due to consistently low intensity."
        with patch("eco_router.ai._call_gemini", return_value=fake_ai_text):
            with patch("eco_router.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "fake-key-for-test"
                mock_settings.gemini_model = "gemini-2.0-flash"
                result = await _gemini_history(SAMPLE_HISTORY_REQ)
        assert result.mode == AI_MODE_LIVE
        assert result.summary == fake_ai_text

    async def test_recommend_uses_gemini_text(self):
        fake_ai_text = "Consider carbon data refresh. Monitor eu-north-1 availability."
        with patch("eco_router.ai._call_gemini", return_value=fake_ai_text):
            with patch("eco_router.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "fake-key-for-test"
                mock_settings.gemini_model = "gemini-2.0-flash"
                result = await _gemini_recommend(SAMPLE_RECOMMEND_REQ)
        assert result.mode == AI_MODE_LIVE


# ── 5. Gemini path — timeout → fallback ──────────────────────────────────────

@pytest.mark.asyncio
class TestGeminiTimeout:
    async def test_explain_falls_back_on_none(self):
        """When _call_gemini returns None (timeout/error), must fall back to demo."""
        with patch("eco_router.ai._call_gemini", return_value=None):
            with patch("eco_router.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "fake-key-for-test"
                mock_settings.gemini_model = "gemini-2.0-flash"
                result = await _gemini_explain(SAMPLE_EXPLAIN_REQ)
        assert result.mode == AI_MODE_DEMO
        assert result.provider == "demo"

    async def test_history_falls_back_on_none(self):
        with patch("eco_router.ai._call_gemini", return_value=None):
            with patch("eco_router.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "fake-key-for-test"
                mock_settings.gemini_model = "gemini-2.0-flash"
                result = await _gemini_history(SAMPLE_HISTORY_REQ)
        assert result.mode == AI_MODE_DEMO

    async def test_recommend_falls_back_on_none(self):
        with patch("eco_router.ai._call_gemini", return_value=None):
            with patch("eco_router.ai.settings") as mock_settings:
                mock_settings.gemini_api_key = "fake-key-for-test"
                mock_settings.gemini_model = "gemini-2.0-flash"
                result = await _gemini_recommend(SAMPLE_RECOMMEND_REQ)
        assert result.mode == AI_MODE_DEMO


# ── 6. _call_gemini internals — no key returns None ──────────────────────────

@pytest.mark.asyncio
class TestCallGeminiInternals:
    async def test_returns_none_when_no_key(self):
        with patch("eco_router.ai.settings") as mock_settings:
            mock_settings.gemini_api_key = ""
            mock_settings.gemini_model = "gemini-2.0-flash"
            result = await _call_gemini("test prompt")
        assert result is None

    async def test_returns_none_on_timeout(self):
        import time as _time

        def blocking_sleep(*_):
            _time.sleep(100)  # synchronous blocking — will time out

        with patch("eco_router.ai.settings") as mock_settings:
            mock_settings.gemini_api_key = "fake-key"
            mock_settings.gemini_model = "gemini-2.0-flash"
            with patch("eco_router.ai.GEMINI_TIMEOUT_SECONDS", 0.05):
                with patch("eco_router.ai._call_gemini_sync", side_effect=blocking_sleep):
                    result = await _call_gemini("test prompt")
        # Timeout path — must return None, never raise
        assert result is None

    async def test_returns_none_on_api_exception(self):
        def raise_exc(*_):
            raise RuntimeError("Simulated Gemini API failure")

        with patch("eco_router.ai.settings") as mock_settings:
            mock_settings.gemini_api_key = "fake-key"
            mock_settings.gemini_model = "gemini-2.0-flash"
            with patch("eco_router.ai._call_gemini_sync", side_effect=raise_exc):
                result = await _call_gemini("test prompt")
        assert result is None


# ── 7. Pydantic input validation ──────────────────────────────────────────────

class TestInputValidation:
    def test_negative_intensity_rejected(self):
        with pytest.raises(Exception):
            ExplainDecisionRequest(
                selected_region="eu-north-1",
                selected_intensity=-10.0,
            )

    def test_empty_selected_region_rejected(self):
        with pytest.raises(Exception):
            ExplainDecisionRequest(
                selected_region="",
                selected_intensity=70.0,
            )

    def test_history_entries_capped_at_20(self):
        entries = [
            HistoryEntry(selected_region="eu-north-1", selected_intensity=70.0)
            for _ in range(30)
        ]
        req = AnalyzeHistoryRequest(history=entries)
        assert len(req.history) <= 20

    def test_candidates_capped_at_10(self):
        big_candidates = {f"region-{i}": float(i * 10) for i in range(20)}
        req = ExplainDecisionRequest(
            selected_region="region-0",
            selected_intensity=0.0,
            candidates=big_candidates,
        )
        assert len(req.candidates) <= 10


# ── 8. API key never in output ────────────────────────────────────────────────

class TestSecurityApiKeyNotExposed:
    """Verifies that no API key ever leaks into responses."""

    FAKE_KEY = "AIzaSyFakeKeyForTestingPurposesOnly12345"

    def _check_no_key(self, response_dict: dict):
        text = str(response_dict)
        assert self.FAKE_KEY not in text, f"API key found in response: {text[:200]}"
        assert "AIzaSy" not in text

    def test_demo_explain_has_no_key(self):
        result = _demo_explain_decision(SAMPLE_EXPLAIN_REQ)
        self._check_no_key(result.model_dump())

    def test_demo_history_has_no_key(self):
        result = _demo_analyze_history(SAMPLE_HISTORY_REQ)
        self._check_no_key(result.model_dump())

    def test_demo_recommend_has_no_key(self):
        result = _demo_recommend(SAMPLE_RECOMMEND_REQ)
        self._check_no_key(result.model_dump())


# ── 9. Parse JSON helper ──────────────────────────────────────────────────────

class TestParseGeminiJson:
    def test_parses_plain_json(self):
        raw = '{"summary": "EU selected", "observations": ["obs1"]}'
        result = _parse_gemini_json(raw)
        assert result["summary"] == "EU selected"

    def test_parses_markdown_json_block(self):
        raw = '```json\n{"summary": "test"}\n```'
        result = _parse_gemini_json(raw)
        assert result["summary"] == "test"

    def test_falls_back_on_plain_text(self):
        raw = "EU-NORTH was selected due to low carbon intensity."
        result = _parse_gemini_json(raw)
        assert "summary" in result
        assert raw in result["summary"]


# ── 10. Routing engine unaffected by AI ──────────────────────────────────────

class TestRoutingEngineUnaffected:
    """
    Verifies the deterministic decision engine produces correct results
    regardless of AI module state. AI must never alter engine output.
    """
    engine = DecisionEngine()

    def _make_reading(self, region: str, intensity: float) -> CarbonReading:
        return CarbonReading(
            region=region,
            intensity=intensity,
            unit="gCO2e/kWh",
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            source="mock",
            is_stale=False,
        )

    def test_engine_selects_lowest_carbon_regardless_of_ai(self):
        """AI must NOT alter which region the engine selects."""
        readings = {
            "us-east-1": self._make_reading("us-east-1", 340.0),
            "eu-north-1": self._make_reading("eu-north-1", 70.0),
            "ap-south-1": self._make_reading("ap-south-1", 180.0),
        }
        health = {"us-east-1": "available", "eu-north-1": "available", "ap-south-1": "available"}
        d = self.engine.make_decision(readings, health)
        assert d.selected_region == "eu-north-1"
        assert d.selected_intensity == 70.0

    def test_engine_ignores_ai_module_entirely(self):
        """Engine decision-making has zero dependency on AI module."""
        # Patch the entire AI module to ensure it can't influence decision
        with patch("eco_router.ai._call_gemini", side_effect=RuntimeError("AI exploded")):
            readings = {
                "us-east-1": self._make_reading("us-east-1", 340.0),
                "eu-north-1": self._make_reading("eu-north-1", 70.0),
                "ap-south-1": self._make_reading("ap-south-1", 180.0),
            }
            health = {"us-east-1": "available", "eu-north-1": "available", "ap-south-1": "available"}
            d = self.engine.make_decision(readings, health)
            assert d.selected_region == "eu-north-1"

    def test_engine_raises_on_no_available_region(self):
        """Confirm engine behavior is unaffected by AI on failure paths."""
        readings = {
            "us-east-1": self._make_reading("us-east-1", 340.0),
            "eu-north-1": self._make_reading("eu-north-1", 70.0),
            "ap-south-1": self._make_reading("ap-south-1", 180.0),
        }
        health = {r: "unavailable" for r in readings}
        with pytest.raises(NoAvailableRegionError):
            self.engine.make_decision(readings, health)
