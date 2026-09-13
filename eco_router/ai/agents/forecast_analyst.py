"""
forecast_analyst.py -- Explains forecast data (stub until Phase C).
"""
from __future__ import annotations
from eco_router.ai.agents.decision_analyst import AgentResponse

AGENT_NAME = "forecast_analyst"


async def analyze(
    forecast: dict,
    gemini_call=None,
) -> AgentResponse:
    tools_used = ["forecast_tools.get_forecast_data"]
    data_sources = ["forecast_module"]

    if not forecast.get("available", False):
        answer = (
            "Carbon intensity forecasting is not yet active. "
            "Once enabled, this agent will analyze predicted intensity trends "
            "and identify future low-carbon routing windows. "
            "Forecasting will use statistical methods (exponential smoothing) on historical readings. "
            "All forecasts will be clearly labelled as PREDICTED, not measured."
        )
        return AgentResponse(
            agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
            answer=answer, confidence=1.0, mode="AI_DEMO_MODE",
        )

    # Future: real forecast analysis here
    return AgentResponse(
        agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
        answer="Forecast analysis not yet implemented.", confidence=0.0, mode="AI_DEMO_MODE",
    )
