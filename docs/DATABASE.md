# Eco-Router — Database Guide

## Overview

Eco-Router uses SQLAlchemy with an async engine.
The default database is **SQLite** (zero-config, no server required).
PostgreSQL is supported for production via environment variable.

## Development (SQLite)

No configuration needed. SQLite is the default.

`.env
DATABASE_URL=sqlite+aiosqlite:///./eco_router.db
`

On startup, `init_db()` calls `Base.metadata.create_all()` — idempotent.

## Production (PostgreSQL)

Install the async driver:

`ash
pip install psycopg[binary]
`

Set in .env:

`
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/eco_router
`

> NEVER commit real credentials. Use environment variables or a secret manager.

## Migrations (Alembic)

Alembic manages schema evolution.

### Initialize (already done)
`ash
alembic init alembic
`

### Run migrations
`ash
alembic upgrade head
`

### Create a new migration
`ash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
`

### Rollback
`ash
alembic downgrade -1   # one step back
alembic downgrade base # full rollback (DESTRUCTIVE)
`

## Tables

| Table | Purpose |
|---|---|
| `users` | Registered dashboard users |
| `routing_decisions` | Carbon-aware routing decisions (time-series) |
| `carbon_measurements` | Per-region carbon intensity readings |
| `region_health` | Latest health check result per region |

## Indexes

Performance indexes on:
- `routing_decisions.timestamp`
- `routing_decisions.selected_region`
- `carbon_measurements.region`
- `carbon_measurements.timestamp`
- `region_health.region`

## Backup

### SQLite
`ash
cp eco_router.db eco_router.backup..db
`

### PostgreSQL
`ash
pg_dump -U user eco_router > backup_.sql
`

## Connection Pooling (PostgreSQL)

SQLAlchemy async engine uses a connection pool automatically.
For high traffic: configure `pool_size`, `max_overflow` in `database.py`.

## Security

- Credentials via environment variables only
- No credentials in code, logs, or git history
- SQLite file excluded from .gitignore
- PostgreSQL: use strong passwords, restrict network access
