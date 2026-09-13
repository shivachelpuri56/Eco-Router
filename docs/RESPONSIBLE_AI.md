# Responsible AI & Responsible Technology — Eco-Router

## Routing Decision: Deterministic, Not AI

The critical routing decision in Eco-Router is **NOT made by an AI/ML model**.

The algorithm is:
1. Get carbon intensity for each available region
2. Sort by intensity (lowest first)
3. Select the minimum
4. Break ties lexicographically

This is a deterministic function. Same input → same output. Every decision is explainable, loggable, and auditable.

**Why this matters:** AI models can hallucinate, produce inconsistent outputs, or fail silently. For infrastructure routing decisions affecting production traffic, determinism and explainability are required properties — not optional features.

## AI Usage Scope

AI is **permitted only** in the following non-critical layers:
- Summarising historical carbon trends
- Explaining past routing decisions in natural language
- Answering sustainability questions from stored data

AI **must never:**
- Override the routing algorithm
- Override availability checks
- Override security constraints (SSRF protection, allowlists)
- Access or transmit API keys or secrets

## Transparency

Every routing decision includes a human-readable `reason` string:

> "Lowest valid carbon intensity (70 gCO₂e/kWh) among 3 available eligible regions."

Every response carries explicit provenance:
- `carbon_data_source: mock | live | cached | stale`
- `simulated: true` in every region response
- `savings_label: ESTIMATED — not a measured real-world emission reduction`

## Data Integrity

| Property | Implementation |
|---|---|
| Simulated data labelled | `source: "mock"`, `simulated: true` |
| Live data sourced | Provider name + timestamp in every reading |
| Stale data flagged | `is_stale: true`, separate `stale` source label |
| Savings labelled estimated | `savings_label: "ESTIMATED"` |
| No fabricated data | Carbon readings always sourced from provider/cache/mock |

## Privacy

- No user personal data is collected or stored
- Request payloads are NOT stored in the database
- Only routing metadata is persisted (region, intensity, latency, success)
- Logs are filtered to prevent accidental secret exposure

## Security

- SSRF: only allowlisted region URLs may be contacted
- Secrets: loaded from environment variables, never hardcoded
- Headers: hop-by-hop headers stripped before forwarding
- Body size: configurable limit (default 10 MB)
- Timeout: enforced on all upstream connections
- Logs: sanitised — API keys and auth headers are never logged

## Human Oversight

- All routing decisions are logged with full audit trail
- Dashboard shows the decision and reason in plain language
- Demo controls allow humans to test and verify the system
- No autonomous action is taken beyond request routing
- The system does not self-modify or self-deploy

## Limitations (Stated Clearly)

1. **Simulated regions**: This is a prototype. The "regions" are local FastAPI servers, not real cloud infrastructure.
2. **Carbon data accuracy**: Mock values are illustrative approximations. Real grids vary by hour and season.
3. **Energy assumption**: `ENERGY_PER_REQUEST_KWH` is a configurable estimate. Actual energy per request varies enormously by workload type.
4. **Savings estimates**: Carbon savings are `ESTIMATED` and `POTENTIAL`. This system does not measure actual emissions reductions.
5. **No lifecycle analysis**: The prototype does not account for embodied carbon, network transit emissions, or hardware manufacturing.
6. **Prototype scope**: Not production-hardened. No authentication. SQLite not suitable for high-volume production.

## Statement on Carbon Claims

> *"Eco-Router demonstrates the potential to reduce workload-associated emissions by routing flexible workloads toward lower-carbon electricity regions. It does not claim to measure the complete lifecycle carbon footprint of a production workload, and all estimated savings are clearly labelled as ESTIMATED — not verified emission reductions."*

## SDG 13 — Climate Action

Eco-Router contributes to SDG 13 by:
1. Demonstrating a replicable pattern for carbon-aware workload routing
2. Making carbon intensity visible in the infrastructure layer
3. Providing an open, educational reference implementation
4. Using responsible claims — never overstating impact
