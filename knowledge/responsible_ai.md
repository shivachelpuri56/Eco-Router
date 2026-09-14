# Responsible AI in Eco-Router

## The core architectural principle
In Eco-Router, there is a strict architectural separation:

  DETERMINISTIC ENGINE → CONTROLS ROUTING
  AI LAYER → EXPLAINS / ANALYZES / RECOMMENDS

The AI system (Eco Intelligence) reads telemetry and generates natural language
explanations, analyses, and recommendations. It NEVER:
- Selects a region for routing
- Overrides the deterministic engine
- Modifies health check status
- Controls any infrastructure state
- Fabricates measurements or telemetry

## Why this matters
If the AI layer fails (API timeout, quota exceeded, network error), routing continues
normally. The deterministic engine is completely independent of the AI layer. This is
tested explicitly: 40+ AI tests verify that engine results are identical regardless of
AI module state.

## Anti-hallucination grounding
Every prompt sent to Gemini includes a system instruction that strictly prohibits:
- Inventing measurements, regions, carbon values, timestamps, or savings figures
- Claiming renewable energy use unless data explicitly states it
- Suggesting routing decisions (the engine controls this)
- Calling estimated savings "actual" or "verified" emission reductions

## The AI Orchestrator
The orchestrator uses deterministic keyword matching to classify user intent (no LLM
for classification). This ensures intent routing is fast, predictable, and testable.

Intent types:
- explain: why was a region selected?
- carbon: what is the current carbon intensity?
- forecast: what is the predicted carbon trend?
- recommend: what engineering improvements can I make?
- knowledge: what is carbon-aware computing / green software?

## Gemini demo mode
When no GEMINI_API_KEY is set, Eco Intelligence operates in AI DEMO MODE. All analysis
is provided by deterministic, template-based responses. The application is fully
functional without any API key. Responses are clearly labelled "AI_DEMO_MODE".

## Data never exposed
- GEMINI_API_KEY is never returned in any API response
- GEMINI_API_KEY is never logged
- API key status is exposed only as a boolean (key present / not present)
