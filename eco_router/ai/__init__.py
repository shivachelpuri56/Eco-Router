"""
Eco Intelligence — AI-powered advisory layer for Eco-Router.

Architecture principle (MANDATORY):
  - The DETERMINISTIC decision engine controls all routing decisions.
  - AI in this module EXPLAINS, ANALYZES, and RECOMMENDS only.
  - AI NEVER selects a region, URL, or infrastructure endpoint.
  - AI NEVER overrides the routing engine.
  - The GEMINI_API_KEY is NEVER exposed to the frontend.

Endpoints:
  POST /ai/explain-decision   → Explain the latest routing decision
  POST /ai/analyze-history    → Summarize routing + carbon patterns
  POST /ai/recommend          → Generate engineering recommendations

Demo Mode:
  When GEMINI_API_KEY is absent or Gemini is unavailable, the module
  returns deterministic template-based analysis clearly labelled
  "AI DEMO MODE". The application works fully without an API key.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from eco_router.config import settings

router = APIRouter(prefix="/ai", tags=["Eco Intelligence"])

# ── Constants ─────────────────────────────────────────────────────────────────

AI_MODE_LIVE = "AI_ANALYSIS"
AI_MODE_DEMO = "AI_DEMO_MODE"
MAX_HISTORY_ITEMS = 20       # cap history sent to Gemini
MAX_PROMPT_CHARS = 6000      # safety limit on prompt length
GEMINI_TIMEOUT_SECONDS = 15  # hard timeout for API calls

# Anti-hallucination system instruction applied to ALL prompts.
GROUNDING_SYSTEM_INSTRUCTION = (
    "You are an AI assistant for Eco-Router, a carbon-aware intelligent load balancer.\n"
    "Your ONLY role is to EXPLAIN, ANALYZE, and RECOMMEND based on the telemetry supplied.\n"
    "STRICT RULES:\n"
    "- Use ONLY the data provided in the prompt. Do NOT invent measurements, regions, "
    "carbon intensity values, timestamps, energy values, costs, savings, or infrastructure states.\n"
    "- Do NOT claim the selected region uses renewable energy unless the data explicitly states it.\n"
    "- Clearly distinguish observed telemetry from interpretations.\n"
    "- Label recommendations as recommendations, not facts.\n"
    "- Never call estimated savings 'actual carbon reduction' or 'verified emissions reduction'.\n"
    "- Do NOT suggest routing decisions. The deterministic engine controls routing.\n"
    "- Be concise and useful to an infrastructure engineer. Avoid marketing language.\n"
    "- Maximum response length: 4 sentences or 80 words per section.\n"
)

# ── Pydantic Input Models ─────────────────────────────────────────────────────

class CandidateInfo(BaseModel):
    region: str
    intensity: float = Field(..., ge=0)


class ExplainDecisionRequest(BaseModel):
    selected_region: str = Field(..., min_length=1, max_length=64)
    selected_intensity: float = Field(..., ge=0)
    carbon_data_source: str = Field(default="mock", max_length=64)
    reason: str = Field(default="", max_length=512)
    candidates: dict[str, float] = Field(default_factory=dict)
    unavailable_regions: list[str] = Field(default_factory=list)
    estimated_savings_gco2e: float | None = Field(default=None, ge=0)

    @field_validator("candidates")
    @classmethod
    def cap_candidates(cls, v: dict) -> dict:
        """Limit candidates to 10 to prevent oversized prompts."""
        return dict(list(v.items())[:10])

    @field_validator("unavailable_regions")
    @classmethod
    def cap_unavailable(cls, v: list) -> list:
        return v[:10]


class HistoryEntry(BaseModel):
    timestamp: str | None = None
    selected_region: str = Field(..., max_length=64)
    selected_intensity: float = Field(..., ge=0)
    carbon_data_source: str = Field(default="mock", max_length=64)
    reason: str | None = Field(default=None, max_length=256)
    estimated_savings_gco2e: float | None = None


class AnalyzeHistoryRequest(BaseModel):
    history: list[HistoryEntry] = Field(default_factory=list)
    carbon_readings: dict[str, float] = Field(default_factory=dict)

    @field_validator("history")
    @classmethod
    def cap_history(cls, v: list) -> list:
        return v[:MAX_HISTORY_ITEMS]

    @field_validator("carbon_readings")
    @classmethod
    def cap_readings(cls, v: dict) -> dict:
        return dict(list(v.items())[:10])


class RecommendRequest(BaseModel):
    history: list[HistoryEntry] = Field(default_factory=list)
    carbon_readings: dict[str, float] = Field(default_factory=dict)
    health_status: dict[str, str] = Field(default_factory=dict)
    total_requests: int = Field(default=0, ge=0)
    routing_by_region: dict[str, int] = Field(default_factory=dict)
    carbon_provider: str = Field(default="mock", max_length=64)

    @field_validator("history")
    @classmethod
    def cap_history(cls, v: list) -> list:
        return v[:MAX_HISTORY_ITEMS]


# ── Structured AI Response Model ─────────────────────────────────────────────

class AIResponse(BaseModel):
    mode: str                        # AI_ANALYSIS or AI_DEMO_MODE
    provider: str                    # "gemini" or "demo"
    title: str
    summary: str
    observations: list[str] = Field(default_factory=list)
    interpretations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "AI explains and analyzes routing telemetry. "
        "Infrastructure routing remains deterministic and policy-controlled. "
        "Carbon savings are estimates, not verified emissions reductions."
    )
    responsible_ai_note: str = (
        "Eco Intelligence is an advisory layer. Human engineer oversight is required. "
        "This system is not an ESG certification tool."
    )


# ── Demo Mode (no Gemini key) ─────────────────────────────────────────────────

def _demo_explain_decision(req: ExplainDecisionRequest) -> AIResponse:
    """Template-based decision explanation using actual telemetry."""
    sel = req.selected_region.upper()
    intensity = req.selected_intensity
    source = req.carbon_data_source

    source_desc = {
        "mock": "simulated grid data",
        "electricity_maps": "live Electricity Maps data",
        "cached": "recently cached data",
        "stale": "older cached data (flagged stale)",
    }.get(source, f"{source} data")

    summary = (
        f"{sel} was selected by the deterministic routing engine because it had the "
        f"lowest valid carbon intensity ({intensity:.0f} gCO\u2082e/kWh) among eligible "
        f"healthy regions, according to {source_desc}."
    )

    observations = [
        f"Selected region: {sel} at {intensity:.0f} gCO\u2082e/kWh",
    ]

    alts = {k: v for k, v in req.candidates.items() if k != req.selected_region}
    if alts:
        sorted_alts = sorted(alts.items(), key=lambda x: x[1])
        for r, v in sorted_alts:
            observations.append(f"Alternative: {r.upper()} at {v:.0f} gCO\u2082e/kWh")

    if req.unavailable_regions:
        observations.append(
            f"Excluded (unavailable): {', '.join(r.upper() for r in req.unavailable_regions)}"
        )

    interpretations = [
        f"Engine reason: {req.reason}" if req.reason else "Standard lowest-carbon selection applied.",
    ]

    if req.estimated_savings_gco2e is not None and req.estimated_savings_gco2e > 0:
        interpretations.append(
            f"ESTIMATED potential saving: {req.estimated_savings_gco2e:.4f} gCO\u2082e "
            f"(based on configured energy-per-request assumption — not a measured reduction)."
        )

    limitations = [
        f"Carbon intensity sourced from {source_desc}.",
        "Estimated savings use a fixed energy-per-request assumption. Actual workload energy may differ.",
    ]

    return AIResponse(
        mode=AI_MODE_DEMO,
        provider="demo",
        title="AI Decision Brief",
        summary=summary,
        observations=observations,
        interpretations=interpretations,
        recommendations=[],
        limitations=limitations,
    )


def _demo_analyze_history(req: AnalyzeHistoryRequest) -> AIResponse:
    """Template-based history analysis using actual telemetry."""
    history = req.history

    if not history:
        return AIResponse(
            mode=AI_MODE_DEMO,
            provider="demo",
            title="Carbon Pattern",
            summary="Insufficient historical data for a reliable pattern analysis.",
            observations=["No routing history available yet."],
            interpretations=[],
            recommendations=["Send test workloads to generate routing history for analysis."],
            limitations=["Analysis requires at least one recorded routing decision."],
        )

    # Aggregate region frequency
    region_counts: dict[str, int] = {}
    intensities_by_region: dict[str, list[float]] = {}
    for h in history:
        region_counts[h.selected_region] = region_counts.get(h.selected_region, 0) + 1
        intensities_by_region.setdefault(h.selected_region, []).append(h.selected_intensity)

    most_selected = max(region_counts, key=region_counts.get)
    most_selected_count = region_counts[most_selected]
    total = len(history)

    avg_intensities = {r: sum(v) / len(v) for r, v in intensities_by_region.items()}
    greenest_region = min(avg_intensities, key=avg_intensities.get)
    greenest_avg = avg_intensities[greenest_region]

    summary = (
        f"Over {total} observed routing decision(s), {most_selected.upper()} was selected "
        f"{most_selected_count} time(s) ({most_selected_count/total*100:.0f}% of decisions), "
        f"likely due to consistently lower carbon intensity."
    )

    observations = [f"Total decisions in sample: {total}"]
    for r, c in sorted(region_counts.items(), key=lambda x: -x[1]):
        avg = avg_intensities.get(r, 0)
        observations.append(f"{r.upper()}: selected {c}× | avg intensity {avg:.0f} gCO\u2082e/kWh")

    interpretations = [
        f"{greenest_region.upper()} showed the lowest average intensity ({greenest_avg:.0f} gCO\u2082e/kWh) "
        "in this sample. Interpretation: this region may have lower-carbon grid electricity, "
        "though this is based on simulated/cached data only."
    ]

    if req.carbon_readings:
        current_min = min(req.carbon_readings, key=req.carbon_readings.get)
        interpretations.append(
            f"Current lowest-intensity region: {current_min.upper()} at "
            f"{req.carbon_readings[current_min]:.0f} gCO\u2082e/kWh."
        )

    limitations = [
        "Pattern based on a small sample — interpret with caution.",
        "Carbon intensities may be simulated and do not reflect real grid conditions.",
    ]

    return AIResponse(
        mode=AI_MODE_DEMO,
        provider="demo",
        title="Carbon Pattern",
        summary=summary,
        observations=observations,
        interpretations=interpretations,
        recommendations=[],
        limitations=limitations,
    )


def _demo_recommend(req: RecommendRequest) -> AIResponse:
    """Template-based engineering recommendations using actual telemetry."""
    recommendations = []

    # Stale-data warning
    if req.carbon_provider == "mock":
        recommendations.append(
            "Consider integrating a real-time carbon intensity provider (e.g., Electricity Maps) "
            "for production deployments to improve routing accuracy."
        )

    # Health observations
    unavailable = [r for r, s in req.health_status.items() if s != "available"]
    if unavailable:
        recommendations.append(
            f"Region(s) currently not available: {', '.join(r.upper() for r in unavailable)}. "
            "Investigate recurring unavailability before expanding routing policy."
        )

    # Routing concentration
    if req.routing_by_region:
        dominant = max(req.routing_by_region, key=req.routing_by_region.get)
        dom_count = req.routing_by_region[dominant]
        total = sum(req.routing_by_region.values())
        if total > 0 and dom_count / total > 0.8:
            recommendations.append(
                f"{dominant.upper()} handles {dom_count}/{total} routed requests. "
                "Consider whether carbon-intensity SLOs should incorporate latency constraints "
                "to avoid over-concentrating workloads in one region."
            )

    # Carbon data freshness
    if req.history:
        recommendations.append(
            "Review carbon data refresh interval if routing decisions consistently target the "
            "same region — stale data can cause suboptimal routing."
        )

    if not recommendations:
        recommendations.append(
            "No specific concerns identified in current telemetry. "
            "Continue monitoring carbon intensity and region health."
        )

    summary = (
        f"Based on {len(req.history)} routing decision(s) and current system state, "
        f"{len(recommendations)} engineering recommendation(s) identified."
    )

    return AIResponse(
        mode=AI_MODE_DEMO,
        provider="demo",
        title="Engineering Insight",
        summary=summary,
        observations=[
            f"Total requests: {req.total_requests}",
            f"Carbon provider: {req.carbon_provider}",
            f"Region health: {req.health_status}",
        ],
        interpretations=[],
        recommendations=recommendations,
        limitations=[
            "Recommendations are advisory only. Human engineer oversight is required.",
            "Do not apply these recommendations without reviewing your specific infrastructure context.",
            "AI cannot and must not modify routing policy, configuration, or infrastructure.",
        ],
    )


# ── Gemini Integration ────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int = MAX_PROMPT_CHARS) -> str:
    """Safety truncation for prompts sent to Gemini."""
    return text[:max_chars] if len(text) > max_chars else text


def _call_gemini_sync(prompt: str, api_key: str, model: str) -> str:
    """Synchronous Gemini call. Must be run in executor."""
    from google import genai as google_genai  # lazy import
    client = google_genai.Client(api_key=api_key)

    full_prompt = GROUNDING_SYSTEM_INSTRUCTION + "\n\n" + prompt
    full_prompt = _truncate(full_prompt)

    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
    )
    return response.text.strip()


def _parse_gemini_json(raw: str) -> dict[str, Any]:
    """
    Attempt to extract a JSON object from Gemini's response.
    Falls back to wrapping the raw text in a summary field.
    Never trusts raw output blindly.
    """
    # Try JSON block extraction
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    # Try bare JSON
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Fallback: wrap text
    return {"summary": raw, "observations": [], "recommendations": [], "limitations": []}


async def _call_gemini(prompt: str) -> str | None:
    """
    Run a Gemini call asynchronously with timeout.
    Returns None on failure — callers fall back to demo mode.
    Never raises to the endpoint handler.
    """
    api_key = settings.gemini_api_key
    model = getattr(settings, "gemini_model", "gemini-2.0-flash")

    if not api_key:
        return None

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _call_gemini_sync, prompt, api_key, model),
            timeout=GEMINI_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("[EcoIntelligence] Gemini call timed out — falling back to demo mode")
        return None
    except Exception as exc:
        # Log the exception type but never log the API key itself
        logger.warning(
            f"[EcoIntelligence] Gemini provider error ({type(exc).__name__}) — "
            "falling back to demo mode"
        )
        return None


# ── Gemini Prompt Builders ────────────────────────────────────────────────────

def _build_explain_prompt(req: ExplainDecisionRequest) -> str:
    alts = {k: v for k, v in req.candidates.items() if k != req.selected_region}
    alt_lines = "\n".join(f"  - {r}: {v:.0f} gCO\u2082e/kWh" for r, v in alts.items()) or "  None"
    unavail = ", ".join(req.unavailable_regions) or "None"
    savings = f"{req.estimated_savings_gco2e:.4f} gCO\u2082e (ESTIMATED)" if req.estimated_savings_gco2e else "N/A"

    return (
        "TASK: Explain the following Eco-Router routing decision in 3-4 sentences for an engineer.\n"
        "Respond with plain text only. Do not add JSON or markdown.\n\n"
        "TELEMETRY (use only this data):\n"
        f"  Selected region: {req.selected_region}\n"
        f"  Selected intensity: {req.selected_intensity:.0f} gCO\u2082e/kWh\n"
        f"  Data source: {req.carbon_data_source}\n"
        f"  Engine reason: {req.reason or 'Lowest-carbon available region'}\n"
        f"  Alternatives considered:\n{alt_lines}\n"
        f"  Unavailable regions: {unavail}\n"
        f"  Estimated potential saving: {savings}\n\n"
        "IMPORTANT: Do not invent values. Do not call estimated savings an actual reduction."
    )


def _build_history_prompt(req: AnalyzeHistoryRequest) -> str:
    if not req.history:
        return (
            "TASK: Report that insufficient routing history is available.\n"
            "Respond in 1 sentence."
        )

    history_lines = []
    for h in req.history[:MAX_HISTORY_ITEMS]:
        ts = h.timestamp or "unknown"
        history_lines.append(
            f"  [{ts}] region={h.selected_region}, intensity={h.selected_intensity:.0f}, "
            f"source={h.carbon_data_source}"
        )

    current_lines = "\n".join(
        f"  {r}: {v:.0f} gCO\u2082e/kWh" for r, v in req.carbon_readings.items()
    ) or "  Not provided"

    return (
        "TASK: Analyze the following Eco-Router routing history and identify patterns. "
        "Respond in 3-4 sentences. Distinguish observed facts from interpretations.\n\n"
        "ROUTING HISTORY (use only this data):\n" + "\n".join(history_lines) + "\n\n"
        "CURRENT CARBON READINGS:\n" + current_lines + "\n\n"
        "IMPORTANT: If data is simulated, say so. Do not invent trends or patterns beyond what the data shows."
    )


def _build_recommend_prompt(req: RecommendRequest) -> str:
    history_lines = []
    for h in req.history[:10]:
        history_lines.append(
            f"  region={h.selected_region}, intensity={h.selected_intensity:.0f}"
        )

    routing_dist = "\n".join(
        f"  {r}: {c} requests" for r, c in req.routing_by_region.items()
    ) or "  No routing data"

    health_lines = "\n".join(
        f"  {r}: {s}" for r, s in req.health_status.items()
    ) or "  No health data"

    return (
        "TASK: Generate 2-3 practical engineering recommendations for an Eco-Router operator. "
        "Label each as a recommendation. Be specific. Respond in plain text.\n\n"
        "SYSTEM TELEMETRY (use only this data):\n"
        f"  Carbon provider: {req.carbon_provider}\n"
        f"  Total requests: {req.total_requests}\n"
        "  Routing distribution:\n" + routing_dist + "\n"
        "  Region health:\n" + health_lines + "\n"
        "  Recent routing sample:\n" + ("\n".join(history_lines) or "  None") + "\n\n"
        "IMPORTANT: Do not suggest specific URLs, regions to remove, or infrastructure changes. "
        "Recommendations must be advisory. Do not modify routing decisions."
    )


# ── Gemini Callsite (with demo fallback) ─────────────────────────────────────

async def _gemini_explain(req: ExplainDecisionRequest) -> AIResponse:
    """Try Gemini for explain-decision; fall back to demo on any failure."""
    model = getattr(settings, "gemini_model", "gemini-2.0-flash")
    prompt = _build_explain_prompt(req)
    raw = await _call_gemini(prompt)

    if raw is None:
        return _demo_explain_decision(req)

    return AIResponse(
        mode=AI_MODE_LIVE,
        provider=f"gemini/{model}",
        title="AI Decision Brief",
        summary=raw,
        observations=[
            f"Selected: {req.selected_region.upper()} at {req.selected_intensity:.0f} gCO\u2082e/kWh",
            f"Data source: {req.carbon_data_source}",
        ],
        interpretations=[],
        recommendations=[],
        limitations=[
            "Carbon intensity may be simulated data.",
            "Estimated savings use a fixed energy-per-request assumption.",
        ],
    )


async def _gemini_history(req: AnalyzeHistoryRequest) -> AIResponse:
    """Try Gemini for history analysis; fall back to demo on any failure."""
    model = getattr(settings, "gemini_model", "gemini-2.0-flash")

    if not req.history:
        return _demo_analyze_history(req)

    prompt = _build_history_prompt(req)
    raw = await _call_gemini(prompt)

    if raw is None:
        return _demo_analyze_history(req)

    return AIResponse(
        mode=AI_MODE_LIVE,
        provider=f"gemini/{model}",
        title="Carbon Pattern",
        summary=raw,
        observations=[f"Sample size: {len(req.history)} routing decision(s)"],
        interpretations=[],
        recommendations=[],
        limitations=[
            "Analysis is based on recent sample only — may not reflect long-term patterns.",
            "Carbon values may be simulated.",
        ],
    )


async def _gemini_recommend(req: RecommendRequest) -> AIResponse:
    """Try Gemini for recommendations; fall back to demo on any failure."""
    model = getattr(settings, "gemini_model", "gemini-2.0-flash")
    prompt = _build_recommend_prompt(req)
    raw = await _call_gemini(prompt)

    if raw is None:
        return _demo_recommend(req)

    return AIResponse(
        mode=AI_MODE_LIVE,
        provider=f"gemini/{model}",
        title="Engineering Insight",
        summary=raw,
        observations=[f"Carbon provider: {req.carbon_provider}"],
        interpretations=[],
        recommendations=[],
        limitations=[
            "Recommendations are advisory. Engineer review required before action.",
            "AI cannot and must not modify routing policy or infrastructure configuration.",
        ],
    )


# ── FastAPI Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/explain-decision",
    summary="AI explanation of the latest routing decision",
    description=(
        "Uses Eco Intelligence to explain the deterministic routing decision "
        "in plain language. Falls back to template-based demo mode when "
        "GEMINI_API_KEY is not configured. "
        "AI NEVER selects or overrides the routing decision."
    ),
)
async def explain_decision(req: ExplainDecisionRequest) -> dict:
    """Explain a routing decision. AI advisory only — no routing control."""
    if settings.gemini_api_key:
        result = await _gemini_explain(req)
    else:
        result = _demo_explain_decision(req)

    return result.model_dump()


@router.post(
    "/analyze-history",
    summary="AI analysis of routing history and carbon patterns",
    description=(
        "Analyzes recent routing decisions and carbon readings to identify "
        "patterns, frequently selected regions, and carbon intensity trends. "
        "Based solely on supplied telemetry — no invented data."
    ),
)
async def analyze_history(req: AnalyzeHistoryRequest) -> dict:
    """Analyze routing history for patterns. AI advisory only."""
    if settings.gemini_api_key:
        result = await _gemini_history(req)
    else:
        result = _demo_analyze_history(req)

    return result.model_dump()


@router.post(
    "/recommend",
    summary="AI engineering recommendations based on routing telemetry",
    description=(
        "Generates practical, advisory engineering recommendations from "
        "routing statistics, carbon readings, and region health data. "
        "Recommendations are non-authoritative and require engineer review."
    ),
)
async def recommend(req: RecommendRequest) -> dict:
    """Generate engineering recommendations. AI advisory only."""
    if settings.gemini_api_key:
        result = await _gemini_recommend(req)
    else:
        result = _demo_recommend(req)

    return result.model_dump()


@router.get(
    "/status",
    summary="Eco Intelligence configuration status",
    description="Returns whether Gemini is configured. Never exposes the API key.",
)
async def ai_status() -> dict:
    """Return AI configuration status — never exposes the key."""
    has_key = bool(settings.gemini_api_key)
    model = getattr(settings, "gemini_model", "gemini-2.0-flash")
    return {
        "eco_intelligence": "enabled",
        "mode": AI_MODE_LIVE if has_key else AI_MODE_DEMO,
        "provider": f"gemini/{model}" if has_key else "demo",
        "gemini_configured": has_key,
        "routing_is_deterministic": True,
        "ai_controls_routing": False,
        "note": (
            "AI explains and analyzes routing telemetry. "
            "Infrastructure routing remains deterministic and policy-controlled."
        ),
    }
