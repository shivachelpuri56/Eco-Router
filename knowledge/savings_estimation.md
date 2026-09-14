# Carbon Savings Estimation Methodology

## How savings are calculated
Eco-Router estimates carbon saved by routing to the cleanest available region instead
of the dirtiest alternative. The calculation uses three inputs:

1. selected_intensity: carbon intensity of the chosen region (gCO2e/kWh)
2. baseline_intensity: carbon intensity of the highest-carbon candidate (gCO2e/kWh)
3. energy_per_request_kwh: estimated energy consumed per request (kWh)

Formula:
  saved_gco2e = (baseline_intensity - selected_intensity) * energy_per_request_kwh

Default energy_per_request_kwh = 0.0001 kWh (0.1 Wh per request), configurable.

## Limitations and caveats (mandatory reading)
These savings figures are ESTIMATED. They represent:
- The theoretical saving if the unselected region had been used instead
- Not actual measured electricity consumption
- Not verified emission reductions
- Not certified carbon credits

The energy_per_request_kwh constant is a rough approximation. Real request energy
varies enormously based on workload type, server utilisation, PUE, and network
transmission energy. A simple API proxy uses far less energy than an ML inference request.

## Why we still include estimates
Even approximate estimates create decision-relevant signal. When eu-north-1 is at
70 gCO2e/kWh and us-east-1 is at 340 gCO2e/kWh, routing to eu-north-1 does produce
real carbon benefit — the estimate captures the direction and rough magnitude even if
the absolute value is uncertain.

## Labels used throughout the system
- "ESTIMATED — not a measured real-world emission reduction" (on every RoutingDecision)
- "PREDICTED" (on every forecast value)
- "AI_DEMO_MODE" (when running without Gemini API key)
- "INSUFFICIENT_DATA" (when fewer than 3 history readings exist for forecasting)
- "simulated: true" (when using mock carbon provider)

## Industry context
The GSF Software Carbon Intensity (SCI) specification provides a more rigorous framework
for measuring software carbon intensity. SCI = (E * I) + M where E is energy, I is
carbon intensity, and M is embodied carbon. Eco-Router's savings estimate is a simplified
approximation of the E * I component change.

Reference: https://sci.greensoftware.foundation
