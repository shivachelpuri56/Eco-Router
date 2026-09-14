# Eco-Router Routing Methodology

## Overview
Eco-Router is a carbon-aware intelligent API load balancer. For each incoming request,
it selects the cloud region with the lowest current grid carbon intensity among all
healthy, available regions. This decision is made by a deterministic algorithm — no
machine learning, no randomness, no LLM involvement in routing.

## The routing algorithm (step by step)
1. Load all configured regions from settings
2. Check health status for each region — exclude unavailable and degraded regions
3. Retrieve carbon intensity for each remaining candidate region
4. Exclude regions with no carbon data or invalid intensity values (< 0)
5. Select the candidate with the minimum intensity:
   selected = argmin(candidates, key=intensity)
   Tie-breaking: lexicographic order of region name (deterministic, documented)
6. Compute estimated carbon savings (see below)
7. Route the request to the selected region's upstream URL
8. Record the decision to the database

## Why deterministic?
Deterministic routing is critical for:
- Auditability: every decision can be explained with a simple rule
- Testability: 100% reproducible in unit tests
- Safety: no LLM can accidentally mis-route traffic
- Transparency: clear to operators, auditors, and users

AI in Eco-Router EXPLAINS routing decisions. AI NEVER makes routing decisions.

## Carbon savings estimation
Eco-Router estimates the carbon saved by routing to the cleanest region instead of the
dirtiest available alternative.

Formula:
  baseline_intensity    = max(candidate intensities)
  saved_per_kwh         = baseline_intensity - selected_intensity
  estimated_savings_gco2e = saved_per_kwh * energy_per_request_kwh

Default energy_per_request_kwh = 0.0001 kWh (configurable).

IMPORTANT: These savings are ESTIMATED. They are NOT verified real-world emission
reductions. The energy value is a configurable assumption, not a measured quantity.
All savings are labelled "ESTIMATED" throughout the system.

## Data sources
- Mock provider: fixed values configured via environment variables (default, no API key needed)
- Electricity Maps: live real-time grid data (requires API key)
- GSF Carbon Aware SDK: self-hosted real-time data (requires SDK URL)

## Regional health
Each region is health-checked every 30 seconds (configurable). A region is excluded from
routing if its health status is not "available". This prevents routing to down or
degraded regions even if they have low carbon intensity.
