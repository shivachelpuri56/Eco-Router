"""
sustainability_advisor.py -- Answers sustainability knowledge questions via RAG.

Phase D upgrade: uses eco_router.rag for BM25 retrieval from knowledge/ files.
Falls back to the built-in compact knowledge corpus if RAG index is empty.

PRINCIPLE: AI EXPLAINS. AI NEVER CONTROLS ROUTING.
"""
from __future__ import annotations
from eco_router.ai.agents.decision_analyst import AgentResponse

AGENT_NAME = "sustainability_advisor"

# Compact fallback knowledge (used when knowledge/ index is empty or RAG fails)
FALLBACK_KNOWLEDGE: dict[str, str] = {
    "carbon_aware_computing": (
        "Carbon-aware computing schedules workloads based on real-time grid carbon intensity. "
        "When grids are greener (more renewables), workloads are preferred. "
        "This reduces the carbon footprint of computing without reducing computation. "
        "Core principle of the Green Software Foundation."
    ),
    "grid_carbon_intensity": (
        "Grid carbon intensity (gCO2e/kWh) measures carbon emissions per unit of electricity. "
        "Nordic grids: 30-80 gCO2e/kWh (hydro/nuclear). US East: 280-420 gCO2e/kWh. "
        "India South: 500-700 gCO2e/kWh (coal). Source: Electricity Maps, IEA."
    ),
    "eco_router_methodology": (
        "Eco-Router selects the cloud region with the lowest current grid carbon intensity "
        "among healthy, available regions. Algorithm: deterministic argmin on intensity. "
        "Carbon savings are ESTIMATED using energy_per_request_kwh (default 0.0001 kWh). "
        "AI explains decisions. AI never controls routing."
    ),
    "savings_estimation": (
        "Savings = (baseline_intensity - selected_intensity) * energy_per_request_kwh. "
        "Baseline = highest-carbon candidate. Values are ESTIMATED — not verified reductions. "
        "SCI specification provides a more rigorous framework: https://sci.greensoftware.foundation"
    ),
    "responsible_ai": (
        "Eco-Router uses strict AI/infrastructure separation. "
        "AI (Eco Intelligence) explains and analyzes only. "
        "The deterministic engine controls all routing. "
        "AI failures do not affect routing. Tested with 40+ explicit independence tests."
    ),
    "green_software": (
        "GSF green software principles: carbon efficiency, energy efficiency, carbon awareness, "
        "hardware efficiency, measurement, climate commitments. "
        "Eco-Router implements carbon awareness (spatial shifting). "
        "References: greensoftware.foundation, SCI spec: sci.greensoftware.foundation"
    ),
}

FALLBACK_KEYWORDS: dict[str, str] = {
    "carbon aware": "carbon_aware_computing",
    "carbon-aware": "carbon_aware_computing",
    "what is carbon": "carbon_aware_computing",
    "grid": "grid_carbon_intensity",
    "gco2": "grid_carbon_intensity",
    "intensity mean": "grid_carbon_intensity",
    "how does eco-router": "eco_router_methodology",
    "how does eco router": "eco_router_methodology",
    "methodology": "eco_router_methodology",
    "algorithm": "eco_router_methodology",
    "savings": "savings_estimation",
    "estimated": "savings_estimation",
    "responsible": "responsible_ai",
    "does ai control": "responsible_ai",
    "green software": "green_software",
    "gsf": "green_software",
    "sci ": "savings_estimation",
}


def _fallback_retrieve(question: str) -> list[tuple[str, str]]:
    q = question.lower()
    found: dict[str, str] = {}
    for keyword, topic in FALLBACK_KEYWORDS.items():
        if keyword in q and topic not in found:
            found[topic] = FALLBACK_KNOWLEDGE[topic]
    if "eco_router_methodology" not in found:
        found["eco_router_methodology"] = FALLBACK_KNOWLEDGE["eco_router_methodology"]
    return list(found.items())[:3]


async def _rag_retrieve(question: str) -> list[tuple[str, str]]:
    """BM25 retrieval from knowledge/ files. Returns empty list on error."""
    try:
        from eco_router.rag import retrieve
        chunks = await retrieve(question, top_k=3)
        return [(c.source, c.content) for c in chunks]
    except Exception:
        return []


def build_demo_answer(question: str, sources: list[tuple[str, str]]) -> str:
    if not sources:
        return (
            f"I don't have specific knowledge about '{question[:100]}'. "
            "Try asking about: carbon-aware computing, grid carbon intensity, "
            "Eco-Router methodology, savings estimation, or responsible AI."
        )
    topic, content = sources[0]
    return f"{content} (Source: {topic.replace('_', ' ').title()})"


def build_gemini_prompt(question: str, sources: list[tuple[str, str]]) -> str:
    context = "\n\n".join(
        f"[SOURCE: {topic}]\n{content}" for topic, content in sources
    )
    return (
        f"RETRIEVED KNOWLEDGE SOURCES:\n\n{context}\n\n"
        f"USER QUESTION: {question}\n\n"
        "Answer using ONLY the retrieved sources above. "
        "If the answer is not in the sources, say so. "
        "Do not invent facts. Cite the source topic used. Keep to 4 sentences."
    )


# Public: expose for /ai/knowledge/search endpoint
def retrieve_relevant_knowledge(question: str) -> list[tuple[str, str]]:
    """Synchronous fallback retrieval (used by knowledge search endpoint)."""
    return _fallback_retrieve(question)


async def analyze(
    question: str,
    gemini_call=None,
) -> AgentResponse:
    # Try RAG first; fall back to hardcoded knowledge
    sources = await _rag_retrieve(question)
    retrieval_method = "rag_bm25"
    if not sources:
        sources = _fallback_retrieve(question)
        retrieval_method = "fallback_keywords"

    tools_used = [f"rag.retrieve (method={retrieval_method})"]
    data_sources = [f"knowledge:{topic}" for topic, _ in sources]

    if gemini_call is not None and sources:
        prompt = build_gemini_prompt(question, sources)
        result = await gemini_call(prompt)
        if result:
            return AgentResponse(
                agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
                answer=result, confidence=0.88, mode="AI_ANALYSIS",
            )

    return AgentResponse(
        agent=AGENT_NAME, tools_used=tools_used, data_sources=data_sources,
        answer=build_demo_answer(question, sources), confidence=0.95, mode="AI_DEMO_MODE",
    )
