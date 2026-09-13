# Eco-Router — Final Engineering Report

## Architecture Summary

Eco-Router is a carbon-aware intelligent API load balancer that routes flexible workloads toward available infrastructure regions with lower grid carbon intensity.

**Core architectural principle:**

```
CARBON DATA
     ↓
DETERMINISTIC DECISION ENGINE
     ↓
SAFE ROUTING
     ↓
TELEMETRY
     ↓
DATABASE (SQLite/PostgreSQL)
     ↓
PROMETHEUS
     ↓
GRAFANA

independently:

TELEMETRY + KNOWLEDGE
     ↓
AI ORCHESTRATOR (eco_router/ai/)
     ↓
SPECIALIZED AGENTS
     ↓
EXPLANATION / FORECAST / RECOMMENDATION
     ↓
HUMAN
```

AI is **never** in the infrastructure control loop.

---

## Files Added (Phase E–K)

### Phase E — Production Database Path
| File | Description |
|---|---|
| `alembic/versions/8af55aacc837_initial_schema.py` | Full DDL migration (replaced empty stub) |
| `docs/DATABASE.md` | Database configuration and migration guide |
| `requirements.txt` | Added `alembic>=1.13.0` |

### Phase G — Grafana Observability
| File | Description |
|---|---|
| `monitoring/prometheus/prometheus.yml` | Prometheus scrape config |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Grafana datasource auto-provisioning |
| `monitoring/grafana/provisioning/dashboards/dashboards.yml` | Dashboard discovery config |
| `monitoring/grafana/dashboards/eco-router.json` | 12-panel Grafana dashboard |
| `docker-compose.monitoring.yml` | Monitoring compose overlay |
| `docs/OBSERVABILITY.md` | Observability guide |

### Phase H — Cloud Region Abstraction
| File | Description |
|---|---|
| `eco_router/cloud/__init__.py` | Package with get_provider() factory |
| `eco_router/cloud/models.py` | CloudRegion dataclass with safe API serialization |
| `eco_router/cloud/provider.py` | Abstract CloudRegionProvider base |
| `eco_router/cloud/mock_provider.py` | Default mock provider (no credentials) |
| `eco_router/cloud/aws_provider.py` | AWS provider stub (credential-gated) |
| `tests/unit/test_cloud.py` | 19 tests for cloud abstraction |
| `docs/CLOUD_REGIONS.md` | Cloud region documentation |

### Phase J — Voice AI
| File | Description |
|---|---|
| `eco_router/static/index.html` | Voice button, Web Speech API integration, TTS |
| `docs/VOICE_AI.md` | Voice AI documentation |

### Phase K — Premium Dashboard Intelligence
| File | Description |
|---|---|
| `eco_router/static/index.html` | AI Console, Forecast panel, RAG panel, Responsible AI section, Before/After comparison, enhanced history |

### Documentation
| File | Description |
|---|---|
| `docs/PHASE_E_K_IMPLEMENTATION_PLAN.md` | Implementation plan |
| `docs/AI_ARCHITECTURE.md` | AI system architecture |
| `docs/CLOUD_REGIONS.md` | Cloud abstraction guide |
| `docs/VOICE_AI.md` | Voice AI guide |
| `docs/DATABASE.md` | Database guide |
| `docs/OBSERVABILITY.md` | Observability guide |
| `scripts/demo.ps1` | Windows one-command demo |
| `scripts/demo.py` | Cross-platform demo launcher |

---

## Files Modified (Phase E–K)

| File | Change |
|---|---|
| `eco_router/config.py` | Added `region_provider` setting |
| `eco_router/main.py` | Upgraded `/cloud/regions` to use provider abstraction; added `/cloud/regions/{id}` |
| `eco_router/static/index.html` | Major Phase K upgrade (AI Console, Forecast, RAG, Responsible AI, Voice, Comparison, enhanced History) |

---

## Dependencies Added

| Package | Purpose |
|---|---|
| `alembic>=1.13.0` | Database schema migrations |

Optional (not auto-installed):
- `psycopg[binary]` — PostgreSQL async driver (only needed for production PostgreSQL)

---

## API Endpoints

### Existing (preserved)
- `GET /health` — System health
- `GET /carbon` — Carbon intensity per region
- `GET /decision` — Current routing decision
- `GET /metrics` — JSON metrics
- `GET /history` — Routing history
- `POST /proxy/{path}` — Carbon-aware reverse proxy
- `POST /ai/ask` — AI orchestrator
- `POST /ai/explain-decision` — Decision explanation
- `POST /ai/analyze-history` — History analysis
- `POST /ai/recommend` — Engineering recommendations
- `GET /ai/knowledge/search` — RAG knowledge search
- `POST /ai/knowledge/reload` — Reload knowledge index
- `GET /ai/knowledge/status` — Index status
- `GET /forecast` — Carbon forecast all regions
- `GET /forecast/{region}` — Forecast single region
- `GET /observability/status` — Observability state
- `GET /cloud/regions` — Cloud region metadata (upgraded)

### New (Phase H)
- `GET /cloud/regions/{region_id}` — Single region metadata

---

## Database Architecture

- ORM: SQLAlchemy 2.x (async)
- Dev: SQLite + aiosqlite (zero config)
- Prod: PostgreSQL + asyncpg (via DATABASE_URL)
- Migrations: Alembic
- 4 tables: users, routing_decisions, carbon_measurements, region_health
- All tables have appropriate indexes on timestamp and region columns

---

## AI Architecture

- Deterministic intent classification (keyword-based, no LLM for routing)
- 5 specialized agents, each grounded in live telemetry
- Optional Gemini 2.0 Flash integration (AI DEMO MODE without API key)
- BM25 RAG over 6 sustainability knowledge documents
- ETS statistical forecasting (all outputs labelled PREDICTED, NOT MEASURED)
- Voice AI: browser Web Speech API → text → /ai/ask → speechSynthesis (local)
- 15-second timeout on all AI requests
- No AI credentials exposed to frontend

---

## Cloud Architecture

- Pluggable CloudRegionProvider pattern
- MockCloudRegionProvider: default, always available, no credentials
- AWSCloudRegionProvider: credential-gated, graceful fallback to mock
- SSRF protection: target URLs never returned to clients
- Safe metadata-only API responses

---

## Observability Architecture

- 8 Prometheus metrics covering requests, routing, carbon, latency, health, AI, savings, uptime
- Grafana dashboard: 12 panels auto-provisioned from `monitoring/` directory
- Docker Compose overlay: `docker-compose.monitoring.yml`
- Dashboard title: ECO-ROUTER — CARBON AWARE INFRASTRUCTURE
- All savings panels labelled ESTIMATED POTENTIAL SAVINGS

---

## Security Controls

| Control | Status |
|---|---|
| No secrets in frontend HTML | ✅ |
| No API keys in JavaScript | ✅ |
| No credentials in logs | ✅ |
| SSRF: only server-side URLs | ✅ |
| AI cannot control routing | ✅ |
| AI cannot modify infrastructure | ✅ |
| Voice: audio not sent to backend | ✅ |
| Cloud API: no endpoints exposed | ✅ |
| AWS credentials: env only | ✅ |
| Request size limits enforced | ✅ |
| 15-second AI timeout | ✅ |

---

## Responsible AI Controls

1. AI does not control routing decisions
2. AI does not override health checks
3. AI uses supplied telemetry and knowledge sources only
4. Forecasts are labelled FORECAST — PREDICTED, NOT MEASURED
5. Mock data labelled SIMULATED GRID DATA
6. Potential savings labelled ESTIMATED POTENTIAL SAVINGS
7. API keys never exposed to clients
8. Voice audio processed locally by browser
9. Human oversight preserved at all times
10. AI recommendations are advisory only

---

## Test Results

```
PYTEST:
176/176 PASS (0 FAIL)

Breakdown:
  test_ai.py              — AI agents and orchestrator
  test_cloud.py           — Phase H cloud abstraction (19 new)
  test_engine.py          — Deterministic routing engine
  test_forecast.py        — ETS forecasting
  test_orchestrator.py    — Multi-agent orchestration
  test_providers.py       — Carbon providers
  test_rag.py             — BM25 RAG + Prometheus metrics
```

---

## Known Limitations

1. **Simulated regions**: All three cloud regions are local mock servers. No real AWS/GCP/Azure infrastructure.
2. **Mock carbon data**: Default carbon values are simulated (us-east-1: 340, eu-north-1: 70, ap-south-1: 180 gCO2e/kWh).
3. **Savings estimates**: All carbon saving figures are estimates from configurable assumptions. Not verified real-world reductions.
4. **Forecast data requirements**: ETS forecasting requires sufficient routing history. Fresh installations show INSUFFICIENT DATA.
5. **Voice AI browser support**: Web Speech API requires Chrome or Edge. Firefox users must use text input.
6. **AWS provider stub**: AWSCloudRegionProvider returns static metadata. Real region discovery (boto3) not yet implemented.
7. **No Kubernetes manifests**: Phase I not implemented to preserve stability.

---

## Demo Instructions

### Quick Start (no credentials needed)

```bash
# Windows PowerShell
.\scripts\demo.ps1

# Cross-platform Python
python scripts/demo.py
```

### Manual Start

```bash
# Terminal 1: Mock regions
python scripts/start_regions.py

# Terminal 2: Eco-Router
uvicorn eco_router.main:app --host 127.0.0.1 --port 8000

# Browser
open http://127.0.0.1:8000
```

### Docker (includes Prometheus + Grafana)

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up
```

---

## Production Roadmap

1. Replace mock providers with real Electricity Maps API integration
2. Implement boto3-based AWS region discovery in AWSCloudRegionProvider
3. Deploy PostgreSQL with Alembic migrations (`alembic upgrade head`)
4. Configure Grafana alerting for carbon intensity thresholds
5. Add Kubernetes manifests (Phase I)
6. Implement persistent audit log for AI recommendations
7. Add rate limiting on AI endpoints
8. Add user-level routing preferences
9. Integrate Carbon Aware SDK for additional carbon data sources
10. Add webhook notifications for routing failover events
