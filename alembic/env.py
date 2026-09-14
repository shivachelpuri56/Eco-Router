"""
alembic/env.py -- Eco-Router database migration environment.

Supports:
  SQLite (development):    sqlite+aiosqlite:///./eco_router.db
  PostgreSQL (production): postgresql+asyncpg://...

The database URL is read from eco_router.config.settings.database_url
(which reads from .env / environment variables).

To create a new migration:
  alembic revision --autogenerate -m "description"

To apply migrations:
  alembic upgrade head

To downgrade:
  alembic downgrade -1
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import re
import os
import sys

# Ensure eco_router package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load all models so autogenerate can detect them
from eco_router.db_models import Base  # noqa: F401
from eco_router.config import settings

config = context.config

# ── Logging ───────────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata (for autogenerate) ────────────────────────────────────────
target_metadata = Base.metadata


def get_sync_url() -> str:
    """
    Convert async DB URL to a sync URL for Alembic's synchronous connection.
    - aiosqlite  -> sqlite
    - asyncpg    -> psycopg2
    """
    url = settings.database_url
    url = url.replace("sqlite+aiosqlite", "sqlite")
    url = url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting)."""
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to DB and applies migrations)."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
