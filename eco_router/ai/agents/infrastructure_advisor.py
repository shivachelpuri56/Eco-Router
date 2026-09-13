"""
infrastructure_advisor.py -- Provides engineering recommendations from telemetry.

Recommendations are advisory ONLY. Never control routing.
"""
from __future__ import annotations
from eco_router.ai.agents.decision_analyst import AgentResponse

AGENT_NAME = "infrastructure_advisor"


def build_demo_recommendations(decision: dict, health: dict, metrics: dict) -> str:
    recommendations = []

    # Check routing concentration
    region_dist = metrics.get("metrics", {}).get("routing_by_region", {})
    total = sum(region_dist.values()) if region_dist else 0
    if total > 0:
        for region, count in region_dist.items():
            pct = count / total * 100
            if pct > 80:
                recommendations.append(
                    f"RECOMMENDATION: {region.upper()} handles {pct:.0f}% of traffic. "
                    "Consider multi-region load spreading for resilience, "
                    "although carbon optimization may naturally concentrate traffic."
                )
                break

    # Check unavailable regions
    unavailable = health.get("unavailable", [])
    if unavailable:
        recommendations.append(
            f"ALERT: {', '.join(r.upper() for r in unavailable)} "
            f"{'is' if len(unavailable) == 1 else 'are'} currently unavailable. "
            "Investigate upstream health before routing resumes."
        )

    # Carbon spread opportunity
    alts = decision.get("alternatives", {})
    selected_intensity = decision.get("selected_intensity", 0)
    if alts:
        max_alt = max(alts.values())
        spread = max_alt - selected_intensity
        if spread > 100:
            recommendations.append(
                f"OPPORTUNITY: Carbon spread of {spread:.0f} gCO\u2082e/kWh between "
                "cleanest and dirtiest region is significant. "
                "Flexible batch workloads shifted to the cleanest region yield the highest estimated savings."
            )

    # Generic if nothing specific
    if not recommendations:
        recommendations.append(
            "All regions are healthy and carbon routing is operating normally. "
            "Consider enabling real-time Electricity Maps data (CARBON_PROVIDER=electricity_maps) "
            "to replace simulated carbon values with live grid data."
        )

    return " ".join(recommendations)


def build_gemini_prompt(decision: dict, health: dict, metrics: dict, history: dict) -> str:
    region_dist = metrics.get("metrics", {}).get("routing_by_region", {})
    selected = decision.get("selected_region", "unknown")
    intensity = decision.get("selected_intensity", 0)
    unavailable = health.get("unavailable", [])
    alts = decision.get("alternatives", {})
    decisions_count = history.get("count", 0)

    return (
        f"INFRASTRUCTURE TELEMETRY:\n"
        f"  Current selection: {selected} at {intensity:.0f} gCO\u2082e/kWh\n"
        f"  Region alternatives: { {r: f'{v:.0f}' for r, v in alts.items()} }\n"
        f"  Unavailable regions: {unavailable or 'none'}\n"
        f"  Recent routing distribution: {region_dist}\n"
        f"  Decisions analyzed: {decisions_count}\n\n"
        "Provide 2-3 specific, actionable engineering recommendations "
        "based solely on this telemetry. "
        "Recommendations must be advisory only -- you are not controlling routing. "
        "Label savings as ESTIMATED. Do not invent data."
    )


async def analyze(
    decision: dict,
    health: dict,
    metrics: dict,
    history: dict,
    gemini_call=None,
) -> AgentResponse:
    tools_used = [
        "infrastructure_tools.get_current_decision",
        "metrics_tools.get_health_summary",
        "metrics_tools.get_system_metrics",
        "history_tools.get_routing_summary",
    ]
    data_sources = ["decision_engine", "health_state", "routing_db"]

    if gemini_call is not None:
        prompt = build_gemini_prompt(decision, health, metrics, history)
        result = await gemini_call(prompt)
        if result:
            return AgentResponse(
                agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
                answer=result, confidence=0.82, mode="AI_ANALYSIS",
            )

    return AgentResponse(
        agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
        answer=build_demo_recommendations(decision, health, metrics),
        confidence=1.0, mode="AI_DEMO_MODE",
    )
