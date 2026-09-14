"""
test_orchestrator.py -- Tests for the AI multi-agent orchestrator.

Validates:
  - Intent classification correctness (deterministic, no LLM)
  - Each agent runs without error in demo mode
  - Orchestrator returns complete structured response
  - Routing engine is NEVER affected by orchestrator calls
  - API key is NEVER in any response field
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from eco_router.ai.orchestrator import classify_intent, ask, OrchestratorResponse
from eco_router.ai.agents.decision_analyst import build_demo_explanation
from eco_router.ai.agents.carbon_analyst import build_demo_analysis
from eco_router.ai.agents.infrastructure_advisor import build_demo_recommendations
from eco_router.ai.agents.sustainability_advisor import retrieve_relevant_knowledge
from eco_router.decision_engine import DecisionEngine, NoAvailableRegionError
from eco_router.schemas import CarbonReading


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_reading(region, intensity, source="mock", is_stale=False):
    return CarbonReading(
        region=region,
        intensity=intensity,
        unit="gCO2e/kWh",
        timestamp=datetime.now(timezone.utc),
        source=source,
        is_stale=is_stale,
    )


def make_app_state():
    state = MagicMock()
    state.carbon_readings = {
        "us-east-1": make_reading("us-east-1", 340.0),
        "eu-north-1": make_reading("eu-north-1", 70.0),
        "ap-south-1": make_reading("ap-south-1", 180.0),
    }
    state.health_status = {
        "us-east-1": "available",
        "eu-north-1": "available",
        "ap-south-1": "available",
    }
    state.start_time = 0.0
    return state


# ── Intent Classification Tests ───────────────────────────────────────────────

class TestIntentClassification:
    def test_why_question_is_explain(self):
        assert classify_intent("why did you route to eu-north-1?") == "explain"

    def test_explain_keyword(self):
        assert classify_intent("explain the routing decision") == "explain"

    def test_carbon_aware_computing_is_knowledge(self):
        assert classify_intent("what is carbon-aware computing?") == "knowledge"

    def test_methodology_is_knowledge(self):
        assert classify_intent("how does Eco-Router methodology work?") == "knowledge"

    def test_what_is_is_knowledge(self):
        assert classify_intent("what is grid carbon intensity?") == "knowledge"

    def test_forecast_question(self):
        assert classify_intent("what do you forecast for tomorrow?") == "forecast"

    def test_recommend_question(self):
        assert classify_intent("what should I do to improve routing?") == "recommend"

    def test_empty_defaults_to_knowledge(self):
        assert classify_intent("") == "knowledge"

    def test_unknown_defaults_to_knowledge(self):
        assert classify_intent("fjkasdjfklasjd") == "knowledge"

    def test_case_insensitive(self):
        assert classify_intent("WHY WAS EU-NORTH-1 SELECTED?") == "explain"


# ── Agent Demo Mode Tests ─────────────────────────────────────────────────────

class TestDecisionAnalystDemo:
    def make_decision(self):
        return {
            "selected_region": "eu-north-1",
            "selected_intensity": 70.0,
            "alternatives": {"us-east-1": 340.0, "ap-south-1": 180.0},
            "unavailable_regions": [],
            "carbon_data_source": "mock",
            "reason": "Lowest carbon",
        }

    def test_demo_contains_region(self):
        result = build_demo_explanation(self.make_decision())
        assert "eu-north-1" in result.lower() or "EU-NORTH-1" in result

    def test_demo_contains_intensity(self):
        result = build_demo_explanation(self.make_decision())
        assert "70" in result

    def test_demo_contains_disclaimer(self):
        result = build_demo_explanation(self.make_decision())
        assert "carbon intensity" in result.lower()

    def test_unavailable_mentioned(self):
        d = self.make_decision()
        d["unavailable_regions"] = ["us-east-1"]
        result = build_demo_explanation(d)
        assert "unavailable" in result.lower() or "US-EAST-1" in result


class TestCarbonAnalystDemo:
    def make_history(self, count=5):
        return {
            "decisions": [
                {"selected_region": "eu-north-1", "selected_intensity": 70.0}
                for _ in range(count)
            ],
            "count": count,
        }

    def make_comparison(self):
        return {
            "regions_sorted": [
                {"region": "eu-north-1", "intensity": 70.0, "health": "available"},
                {"region": "ap-south-1", "intensity": 180.0, "health": "available"},
                {"region": "us-east-1", "intensity": 340.0, "health": "available"},
            ],
            "cleanest_region": "eu-north-1",
            "dirtiest_region": "us-east-1",
            "carbon_spread_gco2e_kwh": 270.0,
        }

    def test_insufficient_data_message(self):
        result = build_demo_analysis({"decisions": [], "count": 0}, self.make_comparison())
        assert "insufficient" in result.lower()

    def test_analysis_with_data(self):
        result = build_demo_analysis(self.make_history(5), self.make_comparison())
        assert "eu-north-1" in result.lower() or "EU-NORTH-1" in result

    def test_estimated_label_present(self):
        result = build_demo_analysis(self.make_history(5), self.make_comparison())
        assert "ESTIMATED" in result or "simulated" in result.lower()


class TestSustainabilityAdvisorDemo:
    def test_carbon_aware_retrieval(self):
        sources = retrieve_relevant_knowledge("what is carbon-aware computing?")
        topics = [t for t, _ in sources]
        assert "carbon_aware_computing" in topics or "eco_router_methodology" in topics

    def test_savings_retrieval(self):
        sources = retrieve_relevant_knowledge("how are savings estimated?")
        topics = [t for t, _ in sources]
        assert any("savings" in t or "methodology" in t for t in topics)

    def test_always_returns_methodology(self):
        sources = retrieve_relevant_knowledge("completely unrelated question xyz123")
        topics = [t for t, _ in sources]
        assert "eco_router_methodology" in topics

    def test_capped_at_3_sources(self):
        sources = retrieve_relevant_knowledge("carbon intensity grid green software gsf")
        assert len(sources) <= 3


# ── Orchestrator Integration Tests ────────────────────────────────────────────

class TestOrchestratorIntegration:
    @pytest.mark.asyncio
    async def test_explain_question_runs_without_error(self):
        state = make_app_state()
        result = await ask("why was eu-north-1 selected?", state)
        assert isinstance(result, OrchestratorResponse)
        assert result.agent_used == "routing_analyst"
        assert result.answer
        assert result.intent == "explain"

    @pytest.mark.asyncio
    async def test_knowledge_question_runs_without_error(self):
        state = make_app_state()
        result = await ask("what is carbon-aware computing?", state)
        assert isinstance(result, OrchestratorResponse)
        assert result.agent_used == "sustainability_advisor"
        assert result.answer

    @pytest.mark.asyncio
    async def test_recommend_question_runs_without_error(self):
        state = make_app_state()
        result = await ask("what should I do to improve routing?", state)
        assert isinstance(result, OrchestratorResponse)
        assert result.agent_used == "infrastructure_advisor"

    @pytest.mark.asyncio
    async def test_forecast_question_stubs_gracefully(self):
        state = make_app_state()
        result = await ask("what do you forecast for tomorrow?", state)
        assert isinstance(result, OrchestratorResponse)
        assert result.agent_used == "forecast_analyst"
        assert "forecast" in result.answer.lower() or "not yet" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_response_has_all_required_fields(self):
        state = make_app_state()
        result = await ask("explain the current routing decision", state)
        assert result.question
        assert result.intent
        assert result.agent_used
        assert isinstance(result.tools_used, list)
        assert isinstance(result.data_sources, list)
        assert result.answer
        assert 0.0 <= result.confidence <= 1.0
        assert result.mode in ("AI_ANALYSIS", "AI_DEMO_MODE")
        assert result.timestamp
        assert result.disclaimer

    @pytest.mark.asyncio
    async def test_api_key_never_in_response(self):
        state = make_app_state()
        result = await ask("why was eu-north-1 selected?", state)
        import json
        result_json = json.dumps(result.__dict__)
        assert "GEMINI_API_KEY" not in result_json
        # Make sure no actual key values from the env appear
        assert "AIza" not in result_json  # Google API key prefix

    @pytest.mark.asyncio
    async def test_question_length_capped(self):
        state = make_app_state()
        long_q = "a" * 10000
        result = await ask(long_q, state)
        assert result.question  # still runs
        assert len(result.question) <= 512

    @pytest.mark.asyncio
    async def test_empty_question_falls_back_gracefully(self):
        # Empty questions fall through to knowledge agent via default
        state = make_app_state()
        result = await ask("", state)
        # Should still return a valid response
        assert result.answer


# ── Routing Engine Independence ───────────────────────────────────────────────

class TestRoutingEngineUnaffectedByOrchestrator:
    """Verify that orchestrator calls cannot alter routing decisions."""

    @pytest.mark.asyncio
    async def test_engine_result_unchanged_after_orchestrator(self):
        state = make_app_state()
        engine = DecisionEngine()

        # Record decision before orchestrator call
        d_before = engine.make_decision(
            carbon_readings=dict(state.carbon_readings),
            health_status=dict(state.health_status),
        )

        # Run orchestrator (reads data, never writes)
        await ask("why was the region selected?", state)
        await ask("recommend improvements", state)

        # Decision must be identical
        d_after = engine.make_decision(
            carbon_readings=dict(state.carbon_readings),
            health_status=dict(state.health_status),
        )

        assert d_before.selected_region == d_after.selected_region
        assert d_before.selected_intensity == d_after.selected_intensity

    def test_engine_selects_eu_regardless_of_ai(self):
        engine = DecisionEngine()
        carbon = {
            "us-east-1": CarbonReading(
                region="us-east-1", intensity=340, unit="gCO2e/kWh",
                timestamp=datetime.now(timezone.utc), source="mock", is_stale=False
            ),
            "eu-north-1": CarbonReading(
                region="eu-north-1", intensity=70, unit="gCO2e/kWh",
                timestamp=datetime.now(timezone.utc), source="mock", is_stale=False
            ),
            "ap-south-1": CarbonReading(
                region="ap-south-1", intensity=180, unit="gCO2e/kWh",
                timestamp=datetime.now(timezone.utc), source="mock", is_stale=False
            ),
        }
        health = {"us-east-1": "available", "eu-north-1": "available", "ap-south-1": "available"}
        d = engine.make_decision(carbon, health)
        assert d.selected_region == "eu-north-1"
