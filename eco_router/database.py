"""
Async SQLAlchemy engine and session factory.
Works with SQLite (aiosqlite) in development and PostgreSQL in production.
Switch by changing DATABASE_URL in .env.
"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from eco_router.config import settings
from eco_router.db_models import Base

# ── Engine ────────────────────────────────────────────────────────────────────
_connect_args: dict = {}
if "sqlite" in settings.database_url:
    # Required for SQLite to work correctly with async
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=settings.app_env == "development",  # SQL logging in dev only
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """Create all tables. Called once at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
