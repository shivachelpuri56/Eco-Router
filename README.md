# 🌿 Eco-Router
### Carbon-Aware Intelligent API Load Balancer

An independent climate-tech infrastructure project.

---

## One-Line Description

Eco-Router dynamically routes flexible API workloads to the available infrastructure region with the lowest current grid carbon intensity - and uses AI to explain, analyze, and surface engineering insights from its routing telemetry.

---

## Demo

Open -> Send Test Workload -> See Deterministic Routing -> Click Analyze -> View AI Insights

US=340 gCO2e/kWh  |  EU=70 gCO2e/kWh <- SELECTED  |  AP=180 gCO2e/kWh

---

## Problem

Digital infrastructure consumes energy. Different electrical grids have vastly different carbon intensities. A workload routed to a region with 70 gCO2e/kWh instead of 340 gCO2e/kWh uses the same computation with less grid carbon.

Most routing decisions today ignore grid carbon entirely.

---

## Why It Matters

| Region | Example Carbon Intensity |
|---|---|
| `eu-north-1` (Nordic hydro/wind) | **70 gCO2e/kWh** <- selected |
| `ap-south-1` (Mixed grid) | 180 gCO2e/kWh |
| `us-east-1` (Coal/gas mix) | 340 gCO2e/kWh |

Flexible workloads (batch jobs, background tasks, ML inference) can be routed toward cleaner regions without user-facing latency impact.

---

## Solution

CHECK the grid -> COMPARE regions -> CHOOSE the cleanest -> ROUTE -> MEASURE

Eco-Router is a FastAPI-based smart load balancer that:
1. Continuously monitors region health and grid carbon intensity
2. Routes each flexible workload to the lowest-carbon healthy region
3. Records every decision with telemetry (region, intensity, savings estimate)
4. Provides an **Eco Intelligence** AI layer to explain decisions and surface engineering insights

---

## Why AI Is Used

### Traditional routing is right for infrastructure control:
- **Deterministic** - same inputs always yield same outputs
- **Reliable** - no network calls to AI providers in the critical path
- **Auditable** - every decision is explainable from the data alone
- **Safe** - no hallucination risk in infrastructure selection

### AI adds genuine value for intelligence synthesis:
- **Explains decisions** in plain language for engineers and operators
- **Identifies historical patterns** across routing telemetry
- **Surfaces engineering recommendations** that a human might miss in raw data
- **Synthesizes multi-signal context** (carbon trends + health + routing distribution)

### Architecture:

DETERMINISTIC ENGINE -> CONTROLS ROUTING
AI INTELLIGENCE      -> EXPLAINS / ANALYZES / RECOMMENDS

NOT:

AI -> DIRECT INFRASTRUCTURE CONTROL (this would be dangerous)

The AI layer receives **read-only telemetry** from the routing engine. It **cannot**:
- Select a region
- Override a routing decision
- Modify health thresholds
- Change infrastructure configuration
- Write to the database

This separation makes the system both safe and auditable.

---

## Architecture

CLIENT
  |
ECO-ROUTER :8000
  |- Decision Engine (deterministic - always controls routing)
  |- Carbon Cache (TTL + fallback chain)
  |- Health Checker (background worker)
  |- Eco Intelligence (AI advisory - explain / analyze / recommend)
  |- Repository (SQLite)
       |
  |------------------------|
  |  Carbon Providers      |
  |  |- MockProvider       |  <- always works, no API key
  |  |- ElectricityMaps    |  <- optional, real data
  |  |- CarbonAwareSDK     |  <- optional, self-hosted
  |------------------------|
       |
Simulated Regions (local FastAPI servers)
  us-east-1  :9001
  eu-north-1 :9002
  ap-south-1 :9003

---

## Deterministic Routing Engine

The routing engine (`decision_engine.py`) implements:

1. **Health check** - exclude unavailable/degraded regions
2. **Carbon validation** - exclude regions with missing or invalid data
3. **Staleness check** - flag but still use stale data
4. **Selection** - `argmin(carbon_intensity)` over valid candidates
5. **Tie-breaking** - lexicographic for reproducibility
6. **Savings estimation** - `(baseline - selected) * energy_per_request_kwh`

All savings are labelled **ESTIMATED** - not measured carbon reductions.

---

## Eco Intelligence (AI Layer)

### Endpoints

| Endpoint | Description |
|---|---|
| `POST /ai/explain-decision` | Plain-language explanation of the latest routing decision |
| `POST /ai/analyze-history` | Pattern analysis across recent routing history |
| `POST /ai/recommend` | Engineering recommendations based on telemetry |
| `GET /ai/status` | AI configuration status (never exposes key) |

### What it does

**AI Decision Brief** - Explains *why* a region was selected in plain language, grounded in the actual telemetry provided.

**Carbon Pattern** - Identifies frequently selected regions, carbon intensity trends, and unusual routing patterns from historical data.

**Engineering Insight** - Surfaces actionable engineering recommendations: data freshness, routing concentration, recurring failures, and optimization opportunities.

### What it does NOT do

- AI does NOT select regions
- AI does NOT override the deterministic engine
- AI does NOT write to any database or configuration
- AI does NOT control infrastructure

---

## How the AI is Grounded

Every Gemini prompt includes strict grounding rules:

"Use ONLY the data provided in the prompt."
"Do NOT invent measurements, regions, carbon values, or savings."
"Clearly distinguish observed telemetry from interpretations."
"Label recommendations as recommendations, not facts."
"Never call estimated savings 'actual carbon reduction'."
"Do NOT suggest routing decisions."

All inputs are Pydantic-validated before reaching the model. All outputs are returned as structured responses with explicit `mode`, `observations`, `interpretations`, `recommendations`, and `limitations` fields.

---

## Demo Mode

The application works **fully without a Gemini API key**.

| State | Behavior |
|---|---|
| No `GEMINI_API_KEY` | AI DEMO MODE - deterministic template-based analysis |
| `GEMINI_API_KEY` present | AI ANALYSIS MODE - Gemini-powered explanations |
| Gemini timeout / error | Graceful fallback to AI DEMO MODE |

The UI clearly displays the current mode: **AI ANALYSIS** or **AI DEMO MODE**. Demo output is never falsely labelled as live AI.

---

## Features

- ✅ **Carbon-aware routing** - routes to lowest-carbon healthy region
- ✅ **3D interactive Earth** - real-time globe with routing arcs
- ✅ **Failover** - automatically reroutes around unavailable regions
- ✅ **Carbon override** - simulate any scenario with `/demo/carbon`
- ✅ **Health simulation** - bring regions up/down with `/demo/health`
- ✅ **Routing history** - persistent SQLite storage of all decisions
- ✅ **Eco Intelligence** - AI-powered decision explanations and insights
- ✅ **Demo Mode** - runs without any API key
- ✅ **JWT authentication** - secure login and session management
- ✅ **SSRF protection** - clients cannot specify arbitrary upstream URLs
- ✅ **Responsible AI** - grounded, non-hallucinating, advisory-only

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| ASGI Server | Uvicorn |
| Database | SQLite + aiosqlite + SQLAlchemy |
| Config | Pydantic Settings |
| Auth | JWT (python-jose) + bcrypt |
| AI | Google Gemini (google-genai SDK) |
| Frontend | Vanilla HTML/CSS/JS |
| 3D Globe | Three.js + globe.gl |
| Carbon Data | Mock / Electricity Maps / GSF Carbon Aware SDK |
| Logging | Loguru |
| Testing | pytest + pytest-asyncio |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Dashboard |
| `/health` | GET | System health |
| `/carbon` | GET | Current carbon intensity per region |
| `/decision` | GET | Current routing decision (preview) |
| `/metrics` | GET | Routing metrics & savings |
| `/history` | GET | Recent routing decisions |
| `/proxy/{path}` | ANY | Carbon-aware reverse proxy |
| `/demo/carbon` | POST | Override mock carbon value |
| `/demo/health` | POST | Override region health |
| `/ai/explain-decision` | POST | AI decision explanation |
| `/ai/analyze-history` | POST | AI history pattern analysis |
| `/ai/recommend` | POST | AI engineering recommendations |
| `/ai/status` | GET | AI configuration status |
| `/auth/register` | POST | Create account |
| `/auth/login` | POST | Log in |
| `/docs` | GET | OpenAPI / Swagger documentation |

---

## Security

- API keys are never hardcoded, logged, or exposed to frontend JavaScript
- `GEMINI_API_KEY` is server-side only - never in `index.html` or responses
- SSRF protection: `allowed_target_urls` is a server-side allowlist; clients cannot specify arbitrary upstream URLs
- JWT tokens are scoped and expire after 24 hours
- All AI inputs are Pydantic-validated before reaching Gemini
- Provider errors are caught, logged (type only), and gracefully handled - no stack traces in responses

---

## Responsible AI

> **Eco Intelligence is an advisory layer. Infrastructure routing remains deterministic.**

- Carbon savings shown are **estimates** based on configured energy assumptions - not certified emissions reductions
- AI explanations are grounded in supplied telemetry only - the model is explicitly instructed not to invent data
- Every AI response includes `limitations` field disclosing data provenance and estimation caveats
- The routing engine has zero dependency on AI - it works identically whether AI is enabled or not
- Human engineer oversight is always required before acting on AI recommendations

---

## Carbon Calculation

estimated_savings_gco2e = (baseline_intensity - selected_intensity) * energy_per_request_kwh

Where:
- `baseline_intensity` = highest available candidate intensity (gCO2e/kWh)
- `selected_intensity` = selected region intensity (gCO2e/kWh)
- `energy_per_request_kwh` = configurable assumption (default: 0.0001 kWh)

This is a **rough estimate** and is explicitly labelled as such in all API responses, UI, and AI prompts.

---

## Testing

```bash
# Unit tests (no servers needed)
pytest tests/unit/ -v

# Full integration test suite
pytest tests/ -v

# Compliance check (73 points)
python scripts/verify_final.py
