"""
orchestrator.py -- AI Orchestrator for Eco-Router.

Intent classification is DETERMINISTIC (keyword-based) -- not LLM-driven.
This ensures the orchestrator is testable, auditable, and fast.

Flow:
  USER QUESTION
      |
  CLASSIFY INTENT (deterministic keyword matching)
      |
  SELECT AGENT
      |
  CALL TOOLS (gather real telemetry/data)
      |
  CALL AGENT (synthesize with Gemini or demo mode)
      |
  RETURN STRUCTURED RESPONSE

The orchestrator NEVER:
  - Controls routing
  - Exposes API keys
  - Invents telemetry
  - Fabricates data
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field

from loguru import logger
from eco_router.config import settings

# Agents
from eco_router.ai.agents import decision_analyst, carbon_analyst
from eco_router.ai.agents import forecast_analyst, infrastructure_advisor, sustainability_advisor
from eco_router.ai.agents.decision_analyst import AgentResponse

# Tools
from eco_router.ai.tools.carbon_tools import get_carbon_snapshot, get_region_comparison
from eco_router.ai.tools.history_tools import get_routing_history, get_routing_summary
from eco_router.ai.tools.metrics_tools import get_system_metrics, get_health_summary
from eco_router.ai.tools.infrastructure_tools import get_current_decision
from eco_router.ai.tools.forecast_tools import get_forecast_data

GEMINI_TIMEOUT_SECONDS = 15
GROUNDING_SYSTEM_INSTRUCTION = (
    "You are an AI assistant for Eco-Router, a carbon-aware intelligent load balancer.\n"
    "Your ONLY role is to EXPLAIN, ANALYZE, and RECOMMEND based on the telemetry supplied.\n"
    "STRICT RULES:\n"
    "- Use ONLY the data provided in the prompt. Do NOT invent measurements, regions, "
    "carbon intensity values, timestamps, energy values, costs, savings, or infrastructure states.\n"
    "- Do NOT claim the selected region uses renewable energy unless the data explicitly states it.\n"
    "- Label recommendations as recommendations, not facts.\n"
    "- Never call estimated savings 'actual carbon reduction' or 'verified emissions reduction'.\n"
    "- Do NOT suggest routing decisions. The deterministic engine controls routing.\n"
    "- Be concise. Maximum 5 sentences per response.\n"
)

# ── Intent Classification ─────────────────────────────────────────────────────

INTENT_KEYWORDS = {
    # Check explain first — "why" questions are most specific
    "explain": [
        "why", "explain", "reason", "selected", "chose", "chosen", "routed", "decision",
        "explain why", "why did", "why was", "how did you choose", "which region",
    ],
    # Knowledge before carbon so "what is carbon-aware" hits knowledge, not carbon data
    "knowledge": [
        "what is", "what are", "how does", "explain carbon-aware", "explain carbon aware",
        "carbon-aware computing", "green software", "gsf", "responsible ai",
        "methodology", "savings estimate", "how are savings", "why does region",
        "grid intensity", "carbon intensity mean",
    ],
    "carbon": [
        "carbon intensity", "co2", "gco2", "current intensity", "emission",
        "cleanest region", "dirtiest", "highest carbon", "lowest carbon",
        "clean", "dirty", "carbon now",
    ],
    "forecast": [
        "forecast", "predict", "future", "next hour", "tomorrow", "trend", "upcoming",
        "will be", "expected",
    ],
    "recommend": [
        "recommend", "suggestion", "advice", "improve", "optimize", "should i",
        "what should", "action", "fix", "better", "what can i",
    ],
}


def classify_intent(question: str) -> str:
    """
    Deterministic intent classification via keyword matching.
    Returns: explain | carbon | forecast | recommend | knowledge
    Priority order matches the dict above.
    """
    q = question.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return intent
    return "knowledge"  # default to knowledge/sustainability


# ── Gemini Caller ─────────────────────────────────────────────────────────────

def _make_gemini_caller(api_key: str):
    """Returns an async callable that sends a prompt to Gemini."""
    async def _call(prompt: str) -> str | None:
        def _sync() -> str | None:
            try:
                from google import genai as google_genai
                client = google_genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=GROUNDING_SYSTEM_INSTRUCTION + "\n\n" + prompt,
                )
                return response.text.strip() if response.text else None
            except Exception as exc:
                logger.warning(f"[Orchestrator] Gemini call failed: {exc}")
                return None

        try:
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, _sync),
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("[Orchestrator] Gemini timed out")
            return None

    return _call


# ── Orchestrator ──────────────────────────────────────────────────────────────

@dataclass
class OrchestratorResponse:
    question: str
    intent: str
    agent_used: str
    tools_used: list[str]
    data_sources: list[str]
    answer: str
    confidence: float
    mode: str          # AI_ANALYSIS | AI_DEMO_MODE
    timestamp: str
    disclaimer: str = (
        "AI-generated analysis. "
        "Routing decisions are made exclusively by the deterministic Decision Engine. "
        "Carbon savings are ESTIMATED, not measured. "
        "All data is sourced from live telemetry or the knowledge base -- not invented."
    )


async def ask(question: str, app_state: Any) -> OrchestratorResponse:
    """
    Main orchestrator entry point.

    Args:
        question: User's natural-language question
        app_state: FastAPI AppState (read-only access)

    Returns:
        OrchestratorResponse with agent, tools, data, and grounded answer
    """
    start = time.time()
    question = question.strip()[:512]  # safety cap
    intent = classify_intent(question)
    logger.info(f"[Orchestrator] Question='{question[:80]}...' Intent={intent}")

    gemini_call = _make_gemini_caller(settings.gemini_api_key) if settings.gemini_api_key else None

    response: AgentResponse | None = None

    try:
        if intent == "explain":
            decision = await get_current_decision(app_state)
            comparison = await get_region_comparison(app_state)
            response = await decision_analyst.analyze(decision, comparison, gemini_call)

        elif intent == "carbon":
            history = await get_routing_history(limit=20)
            comparison = await get_region_comparison(app_state)
            response = await carbon_analyst.analyze(history, comparison, gemini_call)

        elif intent == "forecast":
            forecast = await get_forecast_data(app_state=app_state)
            response = await forecast_analyst.analyze(forecast, gemini_call)


        elif intent == "recommend":
            decision = await get_current_decision(app_state)
            health = await get_health_summary(app_state)
            metrics = await get_routing_summary()
            history = await get_routing_history(limit=20)
            response = await infrastructure_advisor.analyze(
                decision, health, metrics, history, gemini_call
            )

        else:  # knowledge / sustainability
            response = await sustainability_advisor.analyze(question, gemini_call)

    except Exception as exc:
        logger.error(f"[Orchestrator] Agent error: {exc}")
        response = AgentResponse(
            agent="orchestrator",
            tools_used=[],
            data_sources=[],
            answer=(
                "I encountered an error gathering telemetry. "
                "Please try again or check the /health endpoint."
            ),
            confidence=0.0,
            mode="AI_DEMO_MODE",
        )

    elapsed = round(time.time() - start, 3)
    logger.info(
        f"[Orchestrator] Done: agent={response.agent}, "
        f"mode={response.mode}, elapsed={elapsed}s"
    )

    return OrchestratorResponse(
        question=question,
        intent=intent,
        agent_used=response.agent,
        tools_used=response.tools_used,
        data_sources=response.data_sources,
        answer=response.answer,
        confidence=response.confidence,
        mode=response.mode,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
