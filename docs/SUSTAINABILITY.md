# Sustainability — Eco-Router

## Carbon Intensity: The Core Metric

**Grid carbon intensity** (gCO₂e/kWh) measures how much CO₂ equivalent is emitted per unit of electricity consumed from the grid.

This is the only metric used for routing decisions.

## The Carbon Chain

```
Weather (sun, wind, rain)
        ↓
Electricity Generation Mix
(% renewables vs. fossil fuels at a given moment)
        ↓
Grid Carbon Intensity (gCO₂e/kWh)
        ↓
Carbon-Aware Routing Decision
```

Eco-Router operates at the **grid carbon intensity** level.
Weather is not used directly as a routing signal.

## Why Carbon Intensity Varies

| Source | Approximate Intensity |
|---|---|
| Hydropower | 4–30 gCO₂e/kWh |
| Nuclear | 12 gCO₂e/kWh |
| Wind | 7–15 gCO₂e/kWh |
| Solar PV | 20–50 gCO₂e/kWh |
| Natural Gas | 400–490 gCO₂e/kWh |
| Coal | 820–1050 gCO₂e/kWh |

Nordic countries (Sweden, Norway, Finland) routinely achieve <100 gCO₂e/kWh due to abundant hydro and wind. Coal-heavy grids can exceed 800 gCO₂e/kWh.

This 8–10× difference creates a significant opportunity for carbon-aware workload scheduling.

## Carbon Savings Methodology

```
Baseline intensity    = max(candidate intensities)
                      = 340 gCO₂e/kWh (US-EAST in default scenario)

Selected intensity    = 70 gCO₂e/kWh (EU-NORTH)

Avoided intensity     = 340 - 70 = 270 gCO₂e/kWh

ESTIMATED savings     = Avoided × ENERGY_PER_REQUEST_KWH
                      = 270 × 0.0001 kWh
                      = 0.027 gCO₂e per request (ESTIMATED)
```

### IMPORTANT Caveats

1. `ENERGY_PER_REQUEST_KWH = 0.0001` is a configurable assumption, not a measurement
2. Actual energy per request varies enormously by workload type (ML training vs. a simple API call)
3. All savings are labelled `ESTIMATED POTENTIAL SAVING` — not verified reductions
4. This methodology does not include: network transit, hardware embodied carbon, cooling overhead

## Data Classification

| Label | Meaning |
|---|---|
| `source: "mock"` | SIMULATED — illustrative values, not real grid data |
| `source: "electricity_maps"` | Real-time from Electricity Maps API |
| `source: "carbon_aware_sdk"` | From Green Software Foundation SDK |
| `source: "cached"` | Previously fetched live data, within TTL |
| `source: "stale"` | Cached data older than TTL — used as last resort |
| `is_stale: true` | Data is older than CARBON_CACHE_TTL seconds |

## Potential Scale Impact

If deployed at scale across data centre traffic:
- 1 billion HTTP requests routed to 70 gCO₂e/kWh instead of 340 gCO₂e/kWh
- Energy assumption: 0.0001 kWh/request
- ESTIMATED potential: 27,000 kg CO₂e avoided (ESTIMATED — not a production claim)

This illustrates the concept. Real impact requires:
- Accurate energy measurement per workload type
- Actual workload flexibility assessment
- Verified carbon intensity data
- Accounting for data transfer costs

## SDG 13 — Climate Action

Eco-Router demonstrates how infrastructure engineers can incorporate climate-aware design decisions without waiting for policy changes. The technical capability to route flexibly already exists; Eco-Router provides the carbon intelligence layer.
