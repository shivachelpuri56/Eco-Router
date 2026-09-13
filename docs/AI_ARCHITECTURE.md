# Eco-Router — AI Architecture

## Architectural Principle

`
DETERMINISTIC ENGINE  -->  CONTROLS ROUTING
AI INTELLIGENCE       -->  EXPLAINS / ANALYZES / RECOMMENDS
`

AI is NEVER in the routing control loop.

## Components

### AI Orchestrator (eco_router/ai/orchestrator.py)

- Receives natural language questions via POST /ai/ask
- Classifies intent deterministically (keyword-based)
- Routes to appropriate agent
- Returns structured response

### AI Agents

| Agent | Intent | Purpose |
|---|---|---|
| decision_analyst | explain | Explain why a region was selected |
| carbon_analyst | analyze | Analyze carbon intensity patterns |
| forecast_analyst | forecast | Describe forecast trends |
| infrastructure_advisor | infrastructure | Infrastructure health recommendations |
| sustainability_advisor | sustainability | Sustainability best practices |

### AI Tools

| Tool | Data source |
|---|---|
| carbon_tools | /carbon API |
| history_tools | /history API |
| metrics_tools | /metrics API |
| infrastructure_tools | /health API |
| forecast_tools | /forecast API |

### RAG Knowledge Base (eco_router/rag.py)

BM25 (TF-IDF) retrieval from 6 sustainability documents:
- carbon_aware_computing.md
- eco_router_methodology.md
- green_software.md
- grid_carbon_intensity.md
- responsible_ai.md
- savings_estimation.md

### Forecasting (eco_router/forecast.py)

Statistical exponential smoothing (ETS) on historical carbon readings.
All forecasts labelled FORECAST — PREDICTED, NOT MEASURED.

## Gemini Integration

When GEMINI_API_KEY is set:
- AI agents call Gemini 2.0 Flash for natural language generation
- Prompts are grounded with live telemetry
- Mode badge shows: AI ANALYSIS

When GEMINI_API_KEY is not set (AI DEMO MODE):
- Deterministic template responses used
- No external API calls
- Mode badge shows: AI DEMO MODE

## Security

- GEMINI_API_KEY is server-side only — never in HTML/JS
- AI cannot access arbitrary URLs
- AI cannot modify routing state
- AI cannot override health checks
- AI prompts cannot cause infrastructure actions
- 15-second timeout on all AI requests
