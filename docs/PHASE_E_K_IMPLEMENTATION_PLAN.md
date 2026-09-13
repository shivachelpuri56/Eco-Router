# Eco-Router — Phase E–K Implementation Plan

## Current State Audit (2026-09-12)

### Already Exists (DO NOT duplicate)
- FastAPI, Uvicorn, SQLAlchemy, aiosqlite
- 4 DB models: users, routing_decisions, carbon_measurements, region_health
- Alembic initialized but initial migration is empty (pass stub)
- Prometheus metrics (eco_router/prom_metrics.py)
- BM25 RAG (eco_router/rag.py)
- ETS Forecasting (eco_router/forecast.py)
- AI Orchestrator + 5 agents + 5 tools
- deploy/prometheus.yml + deploy/grafana/ dirs (basic)
- docker-compose.yml with postgres + prometheus + grafana
- Dashboard (index.html, 1186 lines) with globe, AI panel, history
- 157/157 unit tests passing

### Missing / Incomplete
- Phase E: Initial migration file is empty pass stub
- Phase E: psycopg (PostgreSQL async driver) not installed
- Phase E: docs/DATABASE.md missing
- Phase G: monitoring/ directory with Grafana JSON dashboard missing
- Phase G: docs/OBSERVABILITY.md missing
- Phase H: eco_router/cloud/ package missing entirely
- Phase H: docs/CLOUD_REGIONS.md missing
- Phase J: Voice AI (microphone button, Web Speech API) missing
- Phase J: docs/VOICE_AI.md missing
- Phase K: No forecast panel, RAG panel, full AI console, responsible AI section

## Implementation Order
1. Phase E: Fix migration, add psycopg, docs/DATABASE.md
2. Phase H: Cloud abstraction (eco_router/cloud/)
3. Phase G: monitoring/ + Grafana JSON dashboard
4. Phase J: Voice AI (frontend only)
5. Phase K: Premium dashboard (largest change)
6. Documentation
7. Phase I: K8s manifests (additive stub)
