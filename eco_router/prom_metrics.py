"""
prom_metrics.py -- Prometheus metrics for Eco-Router.

PHASE F: Exposes Prometheus-format metrics at GET /metrics.

Metrics registered:
  eco_router_requests_total          counter   (region, status)
  eco_router_routing_decisions_total counter   (region, carbon_source)
  eco_router_carbon_intensity_gauge  gauge     (region)
  eco_router_request_latency_seconds histogram (region)
  eco_router_carbon_savings_gco2e    counter   (ESTIMATED)
  eco_router_region_health_gauge     gauge     (region) 1=available 0=unavailable
  eco_router_uptime_seconds          gauge

No auth by default. Set PROMETHEUS_AUTH_TOKEN in env for bearer token protection.
"""
from __future__ import annotations
import time
from typing import Any

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, CollectorRegistry,
        generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from loguru import logger

# ── Registry ──────────────────────────────────────────────────────────────────

if PROMETHEUS_AVAILABLE:
    _REQUESTS = Counter(
        "eco_router_requests_total",
        "Total proxied requests by region and outcome",
        ["region", "status"],
    )
    _DECISIONS = Counter(
        "eco_router_routing_decisions_total",
        "Total routing decisions by selected region and data source",
        ["region", "carbon_source"],
    )
    _CARBON = Gauge(
        "eco_router_carbon_intensity_gauge",
        "Current carbon intensity per region (gCO2e/kWh)",
        ["region"],
    )
    _LATENCY = Histogram(
        "eco_router_request_latency_seconds",
        "Request latency in seconds by region",
        ["region"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    _SAVINGS = Counter(
        "eco_router_carbon_savings_gco2e_total",
        "Cumulative ESTIMATED carbon savings in gCO2e",
    )
    _HEALTH = Gauge(
        "eco_router_region_health_gauge",
        "Region health: 1=available, 0.5=degraded, 0=unavailable",
        ["region"],
    )
    _UPTIME = Gauge(
        "eco_router_uptime_seconds",
        "Application uptime in seconds",
    )
    _AI_REQUESTS = Counter(
        "eco_router_ai_requests_total",
        "Total AI orchestrator requests by intent and mode",
        ["intent", "mode"],
    )
    logger.info("[Metrics] Prometheus client loaded — metrics enabled")
else:
    logger.warning(
        "[Metrics] prometheus_client not installed — "
        "metrics endpoint returns JSON fallback. "
        "Run: pip install prometheus-client"
    )


# ── Public Instrumentation Functions ─────────────────────────────────────────

def record_request(region: str, status: str) -> None:
    """Call after each proxied request. status: 'success' | 'error'"""
    if PROMETHEUS_AVAILABLE:
        _REQUESTS.labels(region=region, status=status).inc()


def record_decision(region: str, carbon_source: str) -> None:
    """Call after each routing decision."""
    if PROMETHEUS_AVAILABLE:
        _DECISIONS.labels(region=region, carbon_source=carbon_source).inc()


def record_latency(region: str, latency_seconds: float) -> None:
    """Call with measured request latency."""
    if PROMETHEUS_AVAILABLE:
        _LATENCY.labels(region=region).observe(latency_seconds)


def record_savings(estimated_gco2e: float) -> None:
    """Call with ESTIMATED savings value from each routing decision."""
    if PROMETHEUS_AVAILABLE and estimated_gco2e and estimated_gco2e > 0:
        _SAVINGS.inc(estimated_gco2e)


def record_ai_request(intent: str, mode: str) -> None:
    """Call after each /ai/ask invocation."""
    if PROMETHEUS_AVAILABLE:
        _AI_REQUESTS.labels(intent=intent, mode=mode).inc()


def update_carbon_gauges(carbon_readings: dict) -> None:
    """Update carbon intensity gauges from app state. Called by updater worker."""
    if not PROMETHEUS_AVAILABLE:
        return
    for region, reading in carbon_readings.items():
        if reading and reading.intensity is not None:
            _CARBON.labels(region=region).set(reading.intensity)


def update_health_gauges(health_status: dict) -> None:
    """Update health gauges from app state. Called by health worker."""
    if not PROMETHEUS_AVAILABLE:
        return
    health_map = {"available": 1.0, "degraded": 0.5, "unavailable": 0.0, "unknown": 0.0}
    for region, status in health_status.items():
        _HEALTH.labels(region=region).set(health_map.get(status, 0.0))


def update_uptime(start_time: float) -> None:
    """Update uptime gauge."""
    if PROMETHEUS_AVAILABLE:
        _UPTIME.set(time.time() - start_time)


# ── Metrics Output ────────────────────────────────────────────────────────────

def generate_metrics_output() -> tuple[bytes, str]:
    """
    Generate Prometheus-format output.
    Returns (body_bytes, content_type).
    """
    if PROMETHEUS_AVAILABLE:
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
    # Fallback: empty prometheus text format
    return b"# prometheus_client not installed\n", "text/plain; version=0.0.4"


def get_metrics_status() -> dict:
    """Return metrics status for /observability/status."""
    return {
        "prometheus_available": PROMETHEUS_AVAILABLE,
        "metrics_endpoint": "/metrics",
        "content_type": CONTENT_TYPE_LATEST if PROMETHEUS_AVAILABLE else "text/plain",
        "tracked_metrics": [
            "eco_router_requests_total",
            "eco_router_routing_decisions_total",
            "eco_router_carbon_intensity_gauge",
            "eco_router_request_latency_seconds",
            "eco_router_carbon_savings_gco2e_total",
            "eco_router_region_health_gauge",
            "eco_router_uptime_seconds",
            "eco_router_ai_requests_total",
        ] if PROMETHEUS_AVAILABLE else [],
        "note": "Install prometheus-client to enable Prometheus export." if not PROMETHEUS_AVAILABLE else "",
    }
