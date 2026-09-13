# Routing Algorithm — Eco-Router

## Overview

The routing algorithm is **deterministic, explainable, and auditable**. No LLM or opaque ML model is involved in the routing decision.

## Algorithm Steps

```
1. Load all configured regions (us-east-1, eu-north-1, ap-south-1)

2. For each region:
   a. Check health status
   b. If status != "available" → exclude (add to unavailable_regions)
   c. Fetch carbon reading from cache
   d. If reading is None → exclude (add to invalid_data_regions)
   e. If intensity < 0 → exclude (invalid)
   f. If is_stale → warn but include (last resort)

3. From remaining candidates:
   selected = min(intensity, key=lambda r: (candidates[r], r))
   (tie-breaking: lexicographic on region name)

4. Compute estimated savings:
   baseline = max(candidate intensities)
   savings_gco2e = (baseline - selected) × ENERGY_PER_REQUEST_KWH
   Label: ESTIMATED

5. Return RoutingDecision with full audit trail
```

## Tie-Breaking

When two or more regions have identical carbon intensity, the winner is chosen by **lexicographic ordering of the region name**:

```
eu-north-1 (100) vs us-east-1 (100)
→ "eu-north-1" < "us-east-1"
→ eu-north-1 wins
```

This rule is:
- Deterministic (same input → same output)
- Documented (here)
- Configurable (future: prefer-closer-region tie-breaking)

## Availability Takes Priority

```
eu-north-1: 70 gCO₂e/kWh  → UNAVAILABLE ✗
ap-south-1: 180 gCO₂e/kWh → AVAILABLE   ✓
us-east-1:  340 gCO₂e/kWh → AVAILABLE   ✓

Result: ap-south-1 selected
```

**Sustainability optimisation NEVER overrides availability.**

## Carbon Data Freshness

Data older than `CARBON_CACHE_TTL` seconds is marked `is_stale=True`.
Stale data is used only as a last resort, with a warning logged.
The `carbon_data_source` field always indicates: `live | cached | mock | stale`.

## No AI in Routing

AI is not used in the routing decision. The algorithm is a deterministic minimum-selection function with documented tie-breaking. This ensures:
- Full explainability
- Auditability
- No hallucination risk
- Consistent behaviour under any load
