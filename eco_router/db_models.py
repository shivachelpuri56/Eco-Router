"""
SQLAlchemy ORM models (database tables) for Eco-Router.
Designed to run on SQLite (development) and PostgreSQL (production).
The repository layer abstracts all DB access.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Registered users for the dashboard."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class RoutingDecisionRecord(Base):
    """Persisted record of every carbon-aware routing decision."""
    __tablename__ = "routing_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    method = Column(String(10), nullable=False)
    path = Column(Text, nullable=False)

    # Carbon decision
    selected_region = Column(String(64), nullable=False, index=True)
    selected_intensity = Column(Float, nullable=False)
    carbon_data_source = Column(String(32), nullable=False)  # mock|live|cached|stale
    reason = Column(Text, nullable=False)

    # Candidates JSON stored as text (avoids JSON column compat issues)
    candidates_json = Column(Text, nullable=True)         # {"us-east-1": 340, ...}
    unavailable_regions_json = Column(Text, nullable=True)

    # Carbon savings (ESTIMATED)
    baseline_intensity = Column(Float, nullable=True)
    estimated_savings_gco2e = Column(Float, nullable=True)

    # Request outcome
    latency_ms = Column(Float, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    upstream_status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


class CarbonMeasurement(Base):
    """Time-series store of carbon intensity readings per region."""
    __tablename__ = "carbon_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(64), nullable=False, index=True)
    intensity = Column(Float, nullable=False)
    unit = Column(String(16), default="gCO2e/kWh")
    source = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    is_stale = Column(Boolean, default=False, nullable=False)


class RegionHealthRecord(Base):
    """Latest health check result per region."""
    __tablename__ = "region_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(64), nullable=False, index=True)
    status = Column(String(16), nullable=False)   # available|degraded|unavailable
    checked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    response_ms = Column(Float, nullable=True)
