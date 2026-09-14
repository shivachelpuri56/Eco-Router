# Green Software Engineering

## Overview
Green software engineering is a discipline focused on building software systems that
emit the least carbon possible. It encompasses practices across development, architecture,
deployment, and operations.

## The GSF Green Software Practitioner Principles

1. Carbon efficiency
   Do more computation per gram of carbon emitted.
   Prefer efficient algorithms, languages, and runtimes.

2. Energy efficiency
   Use less electricity per unit of work.
   Avoid idle compute, right-size infrastructure, use efficient hardware.

3. Carbon awareness
   Do work when and where the grid is cleanest.
   Temporal shifting: run batch jobs at low-carbon times.
   Spatial shifting: route to low-carbon regions (what Eco-Router does).

4. Hardware efficiency
   Use existing hardware longer. Manufacturing (embodied carbon) dominates lifecycle.
   Prefer shared/multi-tenant infrastructure over dedicated.

5. Measurement
   You cannot manage what you cannot measure.
   Track Software Carbon Intensity (SCI) across releases.

6. Climate commitments
   Understand the difference between carbon neutral (offsets), net zero (deep reductions),
   and 100% renewable (power purchase agreements). These are not equivalent.

## Eco-Router and green software principles
Eco-Router implements carbon awareness (principle 3) for API routing workloads. By routing
flexible API traffic to the lowest-carbon available region, it reduces the effective
carbon intensity of each request without changing the computation.

Carbon awareness is most impactful for:
- Batch and background workloads (can tolerate latency)
- Workloads spanning multiple geographies
- Workloads with many equivalent regional deployments

## SCI — Software Carbon Intensity
SCI = (E * I) + M per unit of work

- E: energy consumed (kWh)
- I: carbon intensity of grid (gCO2e/kWh)
- M: embodied carbon of hardware (amortised)
- per unit: per request, per user, per transaction

Eco-Router reduces I by routing to lower-intensity grids, thus lowering SCI.

## References
- GSF Practitioner Certification: https://learn.greensoftware.foundation
- SCI Specification: https://sci.greensoftware.foundation
- Electricity Maps: https://app.electricitymap.org
- Carbon Aware SDK: https://github.com/Green-Software-Foundation/carbon-aware-sdk
