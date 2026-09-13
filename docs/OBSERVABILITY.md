# Eco-Router — Observability Guide

## Architecture

`
Eco-Router (/metrics)
      |
 Prometheus (scrapes every 10s)
      |
 Grafana (reads from Prometheus)
`

## Quick Start (Docker)

`ash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up
`

| Service | URL |
|---|---|
| Eco-Router | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin / eco_router_admin) |

## Prometheus Metrics

All metrics are exposed at `GET /metrics` (JSON format).

| Metric | Type | Description |
|---|---|---|
| eco_router_requests_total | Counter | Total proxy requests |
| eco_router_routing_decisions_total | Counter | Routing decisions by region |
| eco_router_carbon_intensity_gauge | Gauge | Current intensity per region |
| eco_router_carbon_savings_gco2e_total | Counter | Estimated potential savings |
| eco_router_request_latency_seconds | Histogram | Request latency |
| eco_router_region_health_gauge | Gauge | Region health (1/0.5/0) |
| eco_router_uptime_seconds | Gauge | Application uptime |
| eco_router_ai_requests_total | Counter | AI requests by intent+mode |

> ESTIMATED POTENTIAL SAVINGS are calculated from simulated data.
> Not verified real-world emission reductions.

## Grafana Dashboard

Dashboard: **ECO-ROUTER — CARBON AWARE INFRASTRUCTURE**

12 panels including:
- Total requests counter
- Carbon-aware decisions
- Estimated potential savings
- Uptime
- Carbon intensity gauges per region
- Region health gauges
- Carbon intensity time-series
- Routing distribution pie chart
- Request latency (p95) time-series
- AI request breakdown

## Configuration Files

| File | Purpose |
|---|---|
| monitoring/prometheus/prometheus.yml | Prometheus scrape config |
| monitoring/grafana/provisioning/datasources/prometheus.yml | Grafana datasource |
| monitoring/grafana/provisioning/dashboards/dashboards.yml | Dashboard discovery |
| monitoring/grafana/dashboards/eco-router.json | Dashboard definition |
| docker-compose.monitoring.yml | Monitoring overlay |

## Grafana Password

Set `GRAFANA_PASSWORD` in .env (default: eco_router_admin).
Change in production.
