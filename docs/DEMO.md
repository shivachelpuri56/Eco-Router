# Demo Guide — Eco-Router

## Prerequisites

1. Python 3.11+ with virtual environment activated
2. All dependencies installed (`pip install -r requirements.txt`)

## Step 1: Start Region Servers

Open three terminals (or use start_regions.py):

```bash
# Terminal 1
python regions/server.py --region us-east-1 --port 9001

# Terminal 2
python regions/server.py --region eu-north-1 --port 9002

# Terminal 3
python regions/server.py --region ap-south-1 --port 9003
```

Or all at once:
```bash
python scripts/start_regions.py
```

## Step 2: Start Eco-Router

```bash
uvicorn eco_router.main:app --reload --port 8000
```

## Step 3: Open Dashboard

http://localhost:8000

You will see:
- Carbon intensity for all 3 regions
- Current routing decision (eu-north-1 by default)
- Request stats and estimated savings

## Step 4: Run Automated Demo

```bash
python scripts/demo.py
```

This proves 3 scenarios:
1. EU is greenest → routed to EU
2. EU unavailable → failover to AP
3. Carbon conditions change → US becomes greenest

## Manual curl Examples

```bash
# Send workload
curl -X POST http://localhost:8000/proxy/api/task \
  -H "Content-Type: application/json" \
  -d '{"task":"carbon_report"}'

# Expected response headers:
# X-Eco-Router-Region: eu-north-1
# X-Carbon-Intensity: 70.0
# X-Carbon-Data-Source: mock

# Check carbon readings
curl http://localhost:8000/carbon | python -m json.tool

# Check current decision
curl http://localhost:8000/decision | python -m json.tool

# Scenario: EU becomes unavailable
curl -X POST "http://localhost:8000/demo/health?region=eu-north-1&status=unavailable"

# Send workload again → now routes to AP
curl -X POST http://localhost:8000/proxy/api/task \
  -H "Content-Type: application/json" \
  -d '{"task":"carbon_report"}'

# Scenario: US grid cleans up
curl -X POST "http://localhost:8000/demo/carbon?region=us-east-1&intensity=30"
curl -X POST "http://localhost:8000/demo/health?region=eu-north-1&status=available"
curl http://localhost:8000/decision

# Check metrics
curl http://localhost:8000/metrics | python -m json.tool
```

## API Documentation

http://localhost:8000/docs

## Key Things to Show an Evaluator

1. **Dynamic routing** — change carbon values, watch routing change
2. **Failover** — make EU unavailable, watch AP take over
3. **Structured logs** — show `eco_router_events.jsonl`
4. **Response headers** — X-Eco-Router-Region, X-Carbon-Intensity
5. **Dashboard** — real-time visualization
6. **Deterministic** — same conditions → same decision, every time
