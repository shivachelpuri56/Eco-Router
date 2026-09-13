"""
carbon_analyst.py -- Analyzes carbon trends and regional patterns.
"""
from __future__ import annotations
from eco_router.ai.agents.decision_analyst import AgentResponse

AGENT_NAME = "carbon_analyst"


def build_demo_analysis(history: dict, comparison: dict) -> str:
    decisions = history.get("decisions", [])
    if len(decisions) < 2:
        return (
            "Insufficient routing history for carbon pattern analysis. "
            "Run more workloads to generate telemetry."
        )
    regions_sorted = comparison.get("regions_sorted", [])
    spread = comparison.get("carbon_spread_gco2e_kwh", 0)
    cleanest = comparison.get("cleanest_region", "unknown")
    dirtiest = comparison.get("dirtiest_region", "unknown")

    # Count selections
    counts: dict[str, int] = {}
    for d in decisions:
        r = d.get("selected_region")
        if r:
            counts[r] = counts.get(r, 0) + 1
    total = sum(counts.values())

    dominant = max(counts, key=lambda k: counts[k]) if counts else "unknown"
    dominant_pct = round(counts.get(dominant, 0) / total * 100) if total else 0

    lines = [
        f"Over {total} observed decisions, {dominant.upper()} was selected "
        f"{dominant_pct}% of the time, indicating it consistently has the lowest carbon intensity."
    ]
    if spread > 0:
        lines.append(
            f"The carbon spread between {cleanest.upper()} ({regions_sorted[0]['intensity']:.0f} "
            f"gCO\u2082e/kWh) and {dirtiest.upper()} ({regions_sorted[-1]['intensity']:.0f} "
            f"gCO\u2082e/kWh) is {spread:.0f} gCO\u2082e/kWh, "
            "representing significant potential for carbon-aware routing to matter."
        )
    lines.append(
        "Note: All carbon values are ESTIMATED from simulated or cached data -- "
        "not verified real-time grid measurements."
    )
    return " ".join(lines)


def build_gemini_prompt(history: dict, comparison: dict) -> str:
    decisions = history.get("decisions", [])
    regions_sorted = comparison.get("regions_sorted", [])
    spread = comparison.get("carbon_spread_gco2e_kwh", 0)

    region_lines = "\n".join(
        f"  - {r['region']}: {r['intensity']:.0f} gCO\u2082e/kWh (health: {r['health']})"
        for r in regions_sorted
    )
    counts: dict[str, int] = {}
    for d in decisions:
        r = d.get("selected_region")
        if r:
            counts[r] = counts.get(r, 0) + 1

    return (
        f"CARBON INTENSITY SNAPSHOT:\n{region_lines}\n"
        f"Carbon spread: {spread:.0f} gCO\u2082e/kWh\n\n"
        f"REGION SELECTION COUNTS (last {len(decisions)} decisions):\n"
        + "\n".join(f"  - {k}: {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
        + "\n\nAnalyze the carbon patterns observed. "
        "Identify which regions are most/least carbon-intensive and what the selection trend means. "
        "Keep to 4 sentences. Use only the data provided. "
        "Label all savings as ESTIMATED."
    )


async def analyze(
    history: dict,
    comparison: dict,
    gemini_call=None,
) -> AgentResponse:
    tools_used = ["history_tools.get_routing_history", "carbon_tools.get_region_comparison"]
    data_sources = ["routing_db", "carbon_app_state"]

    if gemini_call is not None:
        prompt = build_gemini_prompt(history, comparison)
        result = await gemini_call(prompt)
        if result:
            return AgentResponse(
                agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
                answer=result, confidence=0.85, mode="AI_ANALYSIS",
            )

    return AgentResponse(
        agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
        answer=build_demo_analysis(history, comparison), confidence=1.0, mode="AI_DEMO_MODE",
    )
