# 🌿 Eco-Router
### Carbon-Aware Intelligent API Load Balancer

An independent climate-tech infrastructure project.

---

## One-Line Description

Eco-Router dynamically routes flexible API workloads to the available infrastructure region with the lowest current grid carbon intensity — and uses AI to explain, analyze, and surface engineering insights from its routing telemetry.

---

## Demo

```
Open → Send Test Workload → See Deterministic Routing → Click Analyze → View AI Insights
```

```
US=340 gCO₂e/kWh  |  EU=70 gCO₂e/kWh ← SELECTED  |  AP=180 gCO₂e/kWh
```

---

## Problem

Digital infrastructure consumes energy. Different electrical grids have vastly different carbon intensities. A workload routed to a region with 70 gCO₂e/kWh instead of 340 gCO₂e/kWh uses the same computation with less grid carbon.

Most routing decisions today ignore grid carbon entirely.

---

## Why It Matters

| Region | Example Carbon Intensity |
|---|---|
| `eu-north-1` (Nordic hydro/wind) | **70 gCO₂e/kWh** ← selected |
| `ap-south-1` (Mixed grid) | 180 gCO₂e/kWh |
| `us-east-1` (Coal/gas mix) | 340 gCO₂e/kWh |

Flexible workloads (batch jobs, background tasks, ML inference) can be routed toward cleaner regions without user-facing latency impact.

---

## Solution

```
CHECK the grid → COMPARE regions → CHOOSE the cleanest → ROUTE → MEASURE
```

Eco-Router is a FastAPI-based smart load balancer that:
1. Continuously monitors region health and grid carbon intensity
2. Routes each flexible workload to the lowest-carbon healthy region
3. Records every decision with telemetry (region, intensity, savings estimate)
4. Provides an **Eco Intelligence** AI layer to explain decisions and surface engineering insights

---

## Why AI Is Used

### Traditional routing is right for infrastructure control:
- **Deterministic** — same inputs always yield same outputs
- **Reliable** — no network calls to AI providers in the critical path
- **Auditable** — every decision is explainable from the data alone
- **Safe** — no hallucination risk in infrastructure selection

### AI adds genuine value for intelligence synthesis:
- **Explains decisions** in plain language for engineers and operators
- **Identifies historical patterns** across routing telemetry
- **Surfaces engineering recommendations** that a human might miss in raw data
- **Synthesizes multi-signal context** (carbon trends + health + routing distribution)

### Architecture:

```
DETERMINISTIC ENGINE → CONTROLS ROUTING
AI INTELLIGENCE     → EXPLAINS / ANALYZES / RECOMMENDS

NOT:

AI → DIRECT INFRASTRUCTURE CONTROL (this would be dangerous)
```

The AI layer receives **read-only telemetry** from the routing engine. It **cannot**:
- Select a region
- Override a routing decision
- Modify health thresholds
- Change infrastructure configuration
- Write to the database

This separation makes the system both safe and auditable.

---

## Architecture

```
CLIENT
  ↓
ECO-ROUTER :8000
  ├─ Decision Engine (deterministic — always controls routing)
  ├─ Carbon Cache (TTL + fallback chain)
  ├─ Health Checker (background worker)
  ├─ Eco Intelligence (AI advisory — explain / analyze / recommend)
  └─ Repository (SQLite)
       ↓
  ┌────────────────────────┐
  │  Carbon Providers       │
  │  ├─ MockProvider        │  ← always works, no API key
  │  ├─ ElectricityMaps     │  ← optional, real data
  │  └─ CarbonAwareSDK      │  ← optional, self-hosted
  └────────────────────────┘
       ↓
Simulated Regions (local FastAPI servers)
  us-east-1  :9001
  eu-north-1 :9002
  ap-south-1 :9003
```

---

## Deterministic Routing Engine

The routing engine (`decision_engine.py`) implements:

1. **Health check** — exclude unavailable/degraded regions
2. **Carbon validation** — exclude regions with missing or invalid data
3. **Staleness check** — flag but still use stale data
4. **Selection** — `argmin(carbon_intensity)` over valid candidates
5. **Tie-breaking** — lexicographic for reproducibility
6. **Savings estimation** — `(baseline − selected) × energy_per_request_kwh`

All savings are labelled **ESTIMATED** — not measured carbon reductions.

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

**AI Decision Brief** — Explains *why* a region was selected in plain language, grounded in the actual telemetry provided.

**Carbon Pattern** — Identifies frequently selected regions, carbon intensity trends, and unusual routing patterns from historical data.

**Engineering Insight** — Surfaces actionable engineering recommendations: data freshness, routing concentration, recurring failures, and optimization opportunities.

### What it does NOT do

- AI does NOT select regions
- AI does NOT override the deterministic engine
- AI does NOT write to any database or configuration
- AI does NOT control infrastructure

---

## How the AI is Grounded

Every Gemini prompt includes strict grounding rules:

```
"Use ONLY the data provided in the prompt."
"Do NOT invent measurements, regions, carbon values, or savings."
"Clearly distinguish observed telemetry from interpretations."
"Label recommendations as recommendations, not facts."
"Never call estimated savings 'actual carbon reduction'."
"Do NOT suggest routing decisions."
```

All inputs are Pydantic-validated before reaching the model. All outputs are returned as structured responses with explicit `mode`, `observations`, `interpretations`, `recommendations`, and `limitations` fields.

---

## Demo Mode

The application works **fully without a Gemini API key**.

| State | Behavior |
|---|---|
| No `GEMINI_API_KEY` | AI DEMO MODE — deterministic template-based analysis |
| `GEMINI_API_KEY` present | AI ANALYSIS MODE — Gemini-powered explanations |
| Gemini timeout / error | Graceful fallback to AI DEMO MODE |

The UI clearly displays the current mode: **AI ANALYSIS** or **AI DEMO MODE**. Demo output is never falsely labelled as live AI.

---

## Features

- ✅ **Carbon-aware routing** — routes to lowest-carbon healthy region
- ✅ **3D interactive Earth** — real-time globe with routing arcs
- ✅ **Failover** — automatically reroutes around unavailable regions
- ✅ **Carbon override** — simulate any scenario with `/demo/carbon`
- ✅ **Health simulation** — bring regions up/down with `/demo/health`
- ✅ **Routing history** — persistent SQLite storage of all decisions
- ✅ **Eco Intelligence** — AI-powered decision explanations and insights
- ✅ **Demo Mode** — runs without any API key
- ✅ **JWT authentication** — secure login and session management
- ✅ **SSRF protection** — clients cannot specify arbitrary upstream URLs
- ✅ **Responsible AI** — grounded, non-hallucinating, advisory-only

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
- `GEMINI_API_KEY` is server-side only — never in `index.html` or responses
- SSRF protection: `allowed_target_urls` is a server-side allowlist; clients cannot specify arbitrary upstream URLs
- JWT tokens are scoped and expire after 24 hours
- All AI inputs are Pydantic-validated before reaching Gemini
- Provider errors are caught, logged (type only), and gracefully handled — no stack traces in responses

---

## Responsible AI

> **Eco Intelligence is an advisory layer. Infrastructure routing remains deterministic.**

- Carbon savings shown are **estimates** based on configured energy assumptions — not certified emissions reductions
- AI explanations are grounded in supplied telemetry only — the model is explicitly instructed not to invent data
- Every AI response includes `limitations` field disclosing data provenance and estimation caveats
- The routing engine has zero dependency on AI — it works identically whether AI is enabled or not
- Human engineer oversight is always required before acting on AI recommendations

---

## Carbon Calculation

```
estimated_savings_gco2e = (baseline_intensity − selected_intensity) × energy_per_request_kwh
```

Where:
- `baseline_intensity` = highest available candidate intensity (gCO₂e/kWh)
- `selected_intensity` = selected region intensity (gCO₂e/kWh)
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
```

**Test coverage:**
- ✅ 40 AI unit tests (demo mode, Gemini paths, security, validation, engine independence)
- ✅ 14 decision engine unit tests
- ✅ Provider unit tests
- ✅ Integration / e2e tests
- ✅ SSRF protection verification
- ✅ No secrets in health response

---

## Local Setup

### Prerequisites
- Python 3.11+
- Git

### Setup

```bash
# Clone
git clone <repo-url>
cd eco-router

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
# Edit .env — add AUTH_SECRET at minimum
```

### Run

**Terminal 1** — Start region servers:
```bash
python regions/server.py --region us-east-1 --port 9001
python regions/server.py --region eu-north-1 --port 9002
python regions/server.py --region ap-south-1 --port 9003
```

**Terminal 2** — Start Eco-Router:
```bash
uvicorn eco_router.main:app --reload --port 8000
```

**Open dashboard:** http://localhost:8000

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AUTH_SECRET` | _(required)_ | JWT signing secret |
| `CARBON_PROVIDER` | `mock` | `mock` \| `electricity_maps` \| `carbon_aware_sdk` |
| `MOCK_CARBON_US_EAST_1` | `340.0` | Mock carbon (gCO₂e/kWh) |
| `MOCK_CARBON_EU_NORTH_1` | `70.0` | Mock carbon (gCO₂e/kWh) |
| `MOCK_CARBON_AP_SOUTH_1` | `180.0` | Mock carbon (gCO₂e/kWh) |
| `CARBON_CACHE_TTL` | `300` | Seconds before data is stale |
| `REQUEST_TIMEOUT` | `10.0` | Upstream timeout (seconds) |
| `ENERGY_PER_REQUEST_KWH` | `0.0001` | ESTIMATED energy per request |
| `ELECTRICITY_MAPS_API_KEY` | _(empty)_ | Optional — for live carbon data |
| `GEMINI_API_KEY` | _(empty)_ | Optional — enables AI ANALYSIS mode |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |

See `.env.example` for the full annotated list.

---

## Deployment

The application works **without any API key** in AI DEMO MODE.

For production:
1. Set `AUTH_SECRET` to a strong random string (`openssl rand -hex 32`)
2. Set `APP_ENV=production`
3. Optionally set `GEMINI_API_KEY` for live AI analysis
4. Optionally set `ELECTRICITY_MAPS_API_KEY` for live carbon data

Docker:
```bash
docker compose up
```

---

## Limitations

- Simulated regions are local FastAPI servers, not real cloud infrastructure
- Carbon savings are ESTIMATED — not measured, certified, or verified emissions reductions
- SQLite is not suitable for production-scale traffic
- Routing is carbon-only; latency is not co-optimised (by design for clarity)
- AI recommendations require human review before action

---

## Future Scope

- Multi-dimensional routing: carbon + latency Pareto optimization
- Time-shifted scheduling: queue workloads for lower-carbon windows
- Real-time carbon forecasting integration
- Multi-provider carbon data consensus
- Production-ready PostgreSQL persistence
- Kubernetes operator for cluster-level carbon-aware scheduling

---

## What Broke / What We Learned

1. **Three.js + globe.gl version pinning** — `three@0.158+` broke UMD bundle compatibility with `globe.gl`; pinned to `three@0.145.0` + `globe.gl@2.26.0`.
2. **bcrypt + passlib** — `bcrypt>=4.0` introduced breaking changes in `passlib`'s bcrypt backend; pinned `bcrypt<4.0.0`.
3. **Gemini SDK import** — lazy import (`from google import genai`) required at call time to avoid hard dependency at startup; app starts cleanly without the package installed.
4. **AI grounding is non-trivial** — even with explicit instructions, LLMs must be given structured telemetry (not free-form prompts) to avoid invented data.
5. **Demo Mode is essential** — evaluators/judges rarely have API keys ready; graceful degradation is a product requirement, not an afterthought.

---

## Project Structure

```
eco-router/
├── eco_router/           # Main FastAPI application
│   ├── main.py           # App + lifespan + all endpoints
│   ├── ai.py             # Eco Intelligence AI layer (3 endpoints)
│   ├── decision_engine.py  # Core deterministic routing algorithm
│   ├── proxy.py          # Reverse proxy + SSRF protection
│   ├── health.py         # Region health checker
│   ├── carbon_cache.py   # Carbon cache + fallback chain
│   ├── config.py         # Pydantic settings (env var based)
│   ├── schemas.py        # Shared Pydantic schemas
│   ├── auth.py           # JWT authentication
│   ├── repository.py     # SQLite async repository
│   ├── providers/        # Carbon data providers
│   └── static/           # Dashboard HTML (index.html)
├── regions/              # Simulated region servers
├── scripts/              # Demo + utility scripts
├── tests/                # Unit + integration + e2e tests
│   ├── unit/
│   │   ├── test_ai.py    # 40 AI tests
│   │   ├── test_engine.py
│   │   └── test_providers.py
│   └── e2e/
└── .env.example          # Documented configuration template
```

---

*Eco-Router — Carbon-Aware Intelligent Load Balancer | Supporting SDG 13: Climate Action*
