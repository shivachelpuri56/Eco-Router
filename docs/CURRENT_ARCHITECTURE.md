# Eco-Router — Current Architecture
*Phase 0 Audit — Generated 2026-09-11*

---

## Overview

Eco-Router is a **carbon-aware intelligent API load balancer / reverse proxy** built with FastAPI. It routes flexible API workloads to the lowest-carbon available region, persists telemetry, and exposes a premium 3D dashboard.

The system is a **working, tested product** with:
- A deterministic carbon-routing engine
- Three simulated cloud regions (local FastAPI servers)
- A premium dashboard with a realistic 3D Earth globe (Three.js / globe.gl)
- JWT-based user authentication
- AI advisory layer (Gemini-powered or demo mode)
- SQLite persistence with a PostgreSQL-ready schema
- Existing Docker Compose setup

---

## Repository Root Layout

```
eco-router/
├── eco_router/          # Main FastAPI application package
│   ├── __init__.py      # Version: "1.0.0"
│   ├── main.py          # FastAPI app, lifespan, core routes (570 lines)
│   ├── ai.py            # Eco Intelligence AI advisory layer (672 lines)
│   ├── auth.py          # JWT authentication
│   ├── carbon_cache.py  # Carbon data cache + provider fallback chain
│   ├── config.py        # Pydantic Settings (env-var driven)
│   ├── database.py      # SQLAlchemy async engine + session factory
│   ├── db_models.py     # ORM models
│   ├── decision_engine.py  # Core deterministic routing algorithm
│   ├── health.py        # Async regional health checker
│   ├── logging_config.py
│   ├── proxy.py         # Carbon-aware reverse proxy + SSRF protection
│   ├── repository.py    # DB access layer
│   ├── schemas.py       # Pydantic response models
│   ├── providers/
│   │   ├── base.py
│   │   ├── mock.py
│   │   ├── electricity_maps.py
│   │   └── carbon_aware.py
│   └── static/
│       ├── index.html   # Main dashboard (49,434 bytes)
│       ├── login.html
│       └── register.html
├── regions/server.py    # Simulated region FastAPI servers
├── tests/unit/          # 64 passing unit tests
├── tests/e2e/           # Integration tests
├── scripts/             # demo.py, verify_final.py, etc.
├── docs/                # Architecture + policy docs
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Core API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/health` | System health |
| GET | `/carbon` | Carbon intensity per region |
| GET | `/decision` | Current routing decision (preview) |
| GET | `/metrics` | Routing metrics |
| GET | `/history` | Recent decisions |
| ANY | `/proxy/{path}` | Carbon-aware reverse proxy (SSRF-protected) |
| POST | `/demo/carbon` | Override mock carbon value |
| POST | `/demo/health` | Override region health |
| GET | `/demo/state` | Simulation state |
| POST | `/ai/insight` | AI routing insight |
| POST | `/ai/explain-decision` | Structured AI explanation |
| POST | `/ai/analyze-history` | AI history analysis |
| POST | `/ai/recommend` | AI recommendations |
| GET | `/ai/status` | AI mode (no key exposure) |
| POST | `/auth/register` | Register |
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Current user |

---

## Deterministic Routing Engine

**THIS IS THE AUTHORITATIVE ROUTING CONTROL. AI MUST NEVER OVERRIDE THIS.**

### Algorithm
```
1. For each region: filter by health_status == "available"
2. Filter by valid carbon reading (not None, intensity >= 0)
3. Flag stale data (warn but still use)
4. selected = min(candidates, key=lambda r: (intensity[r], r))  # lexicographic tie-break
5. savings = (max_intensity - selected_intensity) × energy_per_request_kwh  # ESTIMATED
6. Return RoutingDecision
```

### Verified Test Results (64/64 passing)
- US=340, EU=70, AP=180 → **eu-north-1** ✅
- EU unavailable → **ap-south-1** ✅
- All unavailable → `NoAvailableRegionError` ✅
- Stale data: used with warning ✅
- AI failure: zero effect on engine output ✅

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | Registered dashboard users |
| `routing_decisions` | Every routing decision |
| `carbon_measurements` | Time-series carbon readings |
| `region_health` | Health check history |

- **Dev**: `sqlite+aiosqlite:///./eco_router.db`
- **Prod**: `DATABASE_URL=postgresql+asyncpg://...` (schema-compatible, no Alembic yet)

---

## AI Layer Architecture

```
DETERMINISTIC ENGINE → CONTROLS ROUTING
AI LAYER (eco_router/ai.py) → EXPLAINS / ANALYZES / RECOMMENDS

AI NEVER: selects regions, controls routing, overrides health checks,
          exposes API keys, invents measurements
```

### Providers
1. **Gemini**: `google-genai` SDK. Activated when `GEMINI_API_KEY` is set.
2. **Demo Mode**: Deterministic templates. No external calls. Fully functional.

### Anti-Hallucination System Prompt (applied to all prompts)
- Use ONLY supplied telemetry
- Never invent measurements, regions, or savings values
- Never claim renewable energy unless data states it
- Never suggest routing decisions
- Label recommendations as recommendations, not facts

---

## Configuration (env-var driven, no hardcoded secrets)

| Variable | Default | Notes |
|---|---|---|
| `CARBON_PROVIDER` | `mock` | `mock\|electricity_maps\|carbon_aware_sdk` |
| `DATABASE_URL` | SQLite | Switch to PostgreSQL for production |
| `GEMINI_API_KEY` | `""` | Optional — AI demo mode if absent |
| `GEMINI_MODEL` | `gemini-2.0-flash` | |
| `ELECTRICITY_MAPS_API_KEY` | `""` | Optional live carbon data |
| `AUTH_SECRET` | dev default | Must be changed in production |
| `MOCK_CARBON_*` | 340/70/180 | Simulation values |

---

## Simulated Regions

| Region | Port | Carbon (mock) | Location |
|---|---|---|---|
| `us-east-1` | 9001 | 340 gCO₂e/kWh | Virginia, USA |
| `eu-north-1` | 9002 | 70 gCO₂e/kWh | Stockholm, Sweden |
| `ap-south-1` | 9003 | 180 gCO₂e/kWh | Mumbai, India |

---

## What's Already Present ✅

- FastAPI application with lifespan management
- Deterministic carbon-routing engine (tested)
- Carbon provider abstraction (mock / live / SDK)
- SQLite async database with PostgreSQL-compatible schema
- JWT authentication (HTTPOnly cookies, bcrypt passwords)
- SSRF protection (server-side allowlist)
- Premium 3D globe dashboard
- Eco Intelligence AI layer (3 endpoints + grounded demo mode)
- Docker + Docker Compose
- 64 unit tests passing
- 73-point compliance verification script
- Loguru structured logging
- Carbon data caching with TTL
- Background health checker + carbon updater
- Regional failover
- Demo control API

---

## What's Missing (Target State)

| Feature | Phase | Priority |
|---|---|---|
| AI multi-agent orchestrator (`eco_router/ai/`) | B | High |
| Carbon forecasting (`eco_router/forecast.py`) | C | High |
| RAG knowledge system (`eco_router/rag/`) | D | High |
| Alembic DB migrations | E | Medium |
| PostgreSQL in docker-compose | E | Medium |
| Prometheus metrics endpoint | F | High |
| Grafana dashboard + config | G | Medium |
| AWS region abstraction | H | Medium |
| Kubernetes manifests (`k8s/`) | I | Medium |
| Voice AI interface | J | Low |
| Dashboard enhancements (forecast chart, voice btn) | K | Medium |

---

## Security Status

| Control | Status | Notes |
|---|---|---|
| Secrets in env only | ✅ | `.env` gitignored |
| SSRF protection | ✅ | Server-side allowlist |
| JWT HTTPOnly cookies | ✅ | `secure=True` in production |
| Password hashing | ✅ | bcrypt |
| API key never exposed | ✅ | Not in responses or logs |
| Pydantic input validation | ✅ | All AI endpoints |
| CORS | ⚠️ | Currently `allow_origins=["*"]` |
| Rate limiting | ❌ | Not implemented |
| Alembic migrations | ❌ | Not implemented |

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
python regions/server.py --region us-east-1 --port 9001 &
python regions/server.py --region eu-north-1 --port 9002 &
python regions/server.py --region ap-south-1 --port 9003 &
uvicorn eco_router.main:app --port 8000
# → http://localhost:8000

pytest tests/unit/ -v  # 64/64 passing
```

*Generated by Phase 0 repository audit — 2026-09-11*
