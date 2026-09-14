"""initial_schema

Revision ID: 8af55aacc837
Revises:
Create Date: 2026-09-12 00:06:25.794846

This migration creates the full Eco-Router schema from scratch.
It is the baseline migration for both SQLite (development) and
PostgreSQL (production) deployments.

Tables created:
  users              — registered dashboard users
  routing_decisions  — time-series of carbon-aware routing decisions
  carbon_measurements — time-series of per-region carbon readings
  region_health      — latest health check result per region

Indexes added:
  routing_decisions.timestamp        — query by time window
  routing_decisions.selected_region  — filter by region
  carbon_measurements.region         — filter by region
  carbon_measurements.timestamp      — time-window queries
  region_health.region               — latest health per region
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8af55aacc837'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all Eco-Router tables and indexes."""

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ── routing_decisions ──────────────────────────────────────────────────────
    op.create_table(
        'routing_decisions',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('path', sa.Text, nullable=False),
        # Carbon decision
        sa.Column('selected_region', sa.String(64), nullable=False),
        sa.Column('selected_intensity', sa.Float, nullable=False),
        sa.Column('carbon_data_source', sa.String(32), nullable=False),
        sa.Column('reason', sa.Text, nullable=False),
        # JSON blobs
        sa.Column('candidates_json', sa.Text, nullable=True),
        sa.Column('unavailable_regions_json', sa.Text, nullable=True),
        # Savings (ESTIMATED)
        sa.Column('baseline_intensity', sa.Float, nullable=True),
        sa.Column('estimated_savings_gco2e', sa.Float, nullable=True),
        # Outcome
        sa.Column('latency_ms', sa.Float, nullable=True),
        sa.Column('success', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('upstream_status_code', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
    )
    op.create_index('ix_routing_decisions_timestamp', 'routing_decisions', ['timestamp'])
    op.create_index('ix_routing_decisions_selected_region', 'routing_decisions', ['selected_region'])

    # ── carbon_measurements ────────────────────────────────────────────────────
    op.create_table(
        'carbon_measurements',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('region', sa.String(64), nullable=False),
        sa.Column('intensity', sa.Float, nullable=False),
        sa.Column('unit', sa.String(16), server_default='gCO2e/kWh'),
        sa.Column('source', sa.String(32), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_stale', sa.Boolean, nullable=False, server_default='0'),
    )
    op.create_index('ix_carbon_measurements_region', 'carbon_measurements', ['region'])
    op.create_index('ix_carbon_measurements_timestamp', 'carbon_measurements', ['timestamp'])

    # ── region_health ──────────────────────────────────────────────────────────
    op.create_table(
        'region_health',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('region', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('response_ms', sa.Float, nullable=True),
    )
    op.create_index('ix_region_health_region', 'region_health', ['region'])


def downgrade() -> None:
    """Drop all Eco-Router tables."""
    op.drop_table('region_health')
    op.drop_table('carbon_measurements')
    op.drop_table('routing_decisions')
    op.drop_table('users')
