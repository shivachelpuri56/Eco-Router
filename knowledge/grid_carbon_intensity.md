# Grid Carbon Intensity

## What is grid carbon intensity?
Grid carbon intensity (measured in gCO2e/kWh — grams of CO2 equivalent per kilowatt-hour)
is the average carbon emissions produced per unit of electricity consumed on the grid.
It varies by geography, time of day, season, and energy source mix.

## Global benchmarks
| Region | Typical Range (gCO2e/kWh) | Main Source |
|--------|--------------------------|-------------|
| Iceland | 20-30 | Geothermal |
| Norway | 20-40 | Hydropower |
| Sweden | 30-80 | Hydro + Nuclear |
| France | 50-100 | Nuclear |
| Germany | 200-400 | Mixed (coal + wind) |
| UK | 100-350 | Mixed (gas + wind) |
| US East (PJM) | 280-420 | Mixed (gas + coal) |
| India (South) | 500-700 | Coal dominant |

Sources: Electricity Maps, UK National Grid ESO, IEA.

## What drives variability?
- Time of day: solar peaks midday, wind varies
- Season: more hydro in spring (snowmelt), less in summer drought
- Demand spikes: cold mornings, hot afternoons → more gas peaker plants
- Grid interconnections: surplus renewable power exported to neighbours

## Why does this matter for cloud computing?
Different cloud regions draw from different grids. AWS eu-north-1 (Stockholm) draws
primarily from the Swedish grid (hydro + nuclear). AWS ap-south-1 (Mumbai) draws from
the Indian southern grid (coal-heavy). The same compute job produces ~10x more carbon
in Mumbai vs Stockholm under default conditions.

## How Eco-Router uses this
Eco-Router reads the current carbon intensity for each configured region (via the mock
provider, Electricity Maps, or GSF SDK) and routes each request to the lowest-intensity
healthy region. The routing decision is deterministic and fully auditable.
