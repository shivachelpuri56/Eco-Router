# Carbon-Aware Computing

## What is carbon-aware computing?
Carbon-aware computing is the practice of scheduling and routing computational workloads
based on the real-time carbon intensity of the electricity grid. When the grid is powered
by more renewables (low carbon intensity), workloads are preferred. When carbon intensity
is high (coal or gas heavy), flexible workloads can be deferred or shifted to cleaner grids.

Carbon-aware computing does not reduce the amount of computation performed. It reduces the
effective carbon footprint of that computation by choosing when and where it runs.

## Key principle
Carbon intensity (gCO2e/kWh) is the central metric. Lower is greener.
A workload running in Stockholm (Sweden, ~30-80 gCO2e/kWh) produces ~5-10x less carbon
than the same workload running in Mumbai (India, ~600-700 gCO2e/kWh).

## Temporal shifting vs spatial shifting
- Temporal shifting: defer a batch job until the grid is cleaner (later tonight when wind picks up)
- Spatial shifting: route the request to the geographically cleanest available region NOW
Eco-Router implements spatial shifting.

## Green Software Foundation
The Green Software Foundation (GSF) defines carbon awareness as one of the core principles
of green software engineering. The GSF Carbon Aware SDK provides open-source tooling for
querying real-time carbon intensity data.

## References
- Green Software Foundation: https://greensoftware.foundation
- Carbon Aware SDK: https://github.com/Green-Software-Foundation/carbon-aware-sdk
- Electricity Maps: https://app.electricitymap.org
