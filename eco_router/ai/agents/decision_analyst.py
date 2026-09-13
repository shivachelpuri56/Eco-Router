"""
decision_analyst.py -- Explains the current routing decision in plain language.

PRINCIPLE: AI EXPLAINS. The deterministic engine DECIDES.
This agent reads routing decision data and returns a grounded explanation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResponse:
    agent: str
    tools_used: list[str]
    data_sources: list[str]
    answer: str
    confidence: float          # 0.0 - 1.0
    mode: str                  # AI_ANALYSIS | AI_DEMO_MODE
    disclaimer: str = (
        "AI-generated explanation. "
        "Routing decisions are made exclusively by the deterministic Decision Engine. "
        "Carbon savings are ESTIMATED, not measured."
    )


AGENT_NAME = "routing_analyst"


def build_demo_explanation(decision: dict) -> str:
    """Deterministic fallback — no LLM required."""
    sel = decision.get("selected_region", "unknown")
    intensity = decision.get("selected_intensity", 0)
    alts = decision.get("alternatives", {})
    unavailable = decision.get("unavailable_regions", [])
    source = decision.get("carbon_data_source", "mock")

    source_note = {
        "mock": "simulated data",
        "live": "live grid data",
        "cached": "cached data",
        "stale": "stale cached data (flagged)",
        "electricity_maps": "live Electricity Maps data",
    }.get(source, f"{source} data")

    lines = [
        f"{sel.upper()} was selected because its grid carbon intensity "
        f"({intensity:.0f} gCO\u2082e/kWh) is the lowest among eligible regions ({source_note})."
    ]
    if alts:
        sorted_alts = sorted(alts.items(), key=lambda x: x[1])
        compared = "; ".join(f"{r.upper()} at {v:.0f}" for r, v in sorted_alts)
        lines.append(f"Other candidates: {compared} gCO\u2082e/kWh.")
    if unavailable:
        lines.append(f"Excluded (unavailable): {', '.join(r.upper() for r in unavailable)}.")
    lines.append("Carbon intensity reflects grid conditions, not a guarantee of renewable energy use.")
    return " ".join(lines)


def build_gemini_prompt(decision: dict, comparison: dict) -> str:
    sel = decision.get("selected_region", "unknown")
    intensity = decision.get("selected_intensity", 0)
    reason = decision.get("reason", "")
    source = decision.get("carbon_data_source", "mock")
    alts = decision.get("alternatives", {})
    unavailable = decision.get("unavailable_regions", [])
    savings = decision.get("estimated_savings_gco2e")

    alt_lines = "\n".join(f"  - {r}: {v:.0f} gCO\u2082e/kWh" for r, v in sorted(alts.items(), key=lambda x: x[1]))
    savings_line = f"  - Estimated savings vs worst alternative: ~{savings:.6f} gCO\u2082e (ESTIMATED)" if savings else ""

    return (
        f"ROUTING DECISION DATA (from deterministic engine -- do not alter):\n"
        f"  Selected region: {sel}\n"
        f"  Carbon intensity: {intensity:.0f} gCO\u2082e/kWh\n"
        f"  Data source: {source}\n"
        f"  Engine reason: {reason}\n"
        f"  Alternative regions:\n{alt_lines}\n"
        f"  Unavailable regions: {', '.join(unavailable) or 'none'}\n"
        f"{savings_line}\n\n"
        "Provide a clear, honest 3-sentence explanation of why this region was selected. "
        "Do NOT invent data. Do NOT suggest a different routing decision."
    )


async def analyze(
    decision: dict,
    comparison: dict,
    gemini_call=None,
) -> AgentResponse:
    """Main agent entry point."""
    tools_used = ["infrastructure_tools.get_current_decision", "carbon_tools.get_region_comparison"]
    data_sources = [decision.get("carbon_data_source", "unknown"), "decision_engine"]

    if gemini_call is not None:
        prompt = build_gemini_prompt(decision, comparison)
        result = await gemini_call(prompt)
        if result:
            return AgentResponse(
                agent=AGENT_NAME,
                tools_used=tools_used,
                data_sources=data_sources,
                answer=result,
                confidence=0.9,
                mode="AI_ANALYSIS",
            )

    # Demo mode fallback
    return AgentResponse(
        agent=AGENT_NAME,
        tools_used=tools_used,
        data_sources=data_sources,
        answer=build_demo_explanation(decision),
        confidence=1.0,
        mode="AI_DEMO_MODE",
    )
