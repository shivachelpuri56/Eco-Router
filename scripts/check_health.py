"""Live integration test against running Eco-Router + regions."""
import httpx, json, time

BASE = "http://127.0.0.1:8000"
PASS = []
FAIL = []

def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")

print("\n=== ECO-ROUTER LIVE INTEGRATION TEST ===\n")

# 1. Health
r = httpx.get(f"{BASE}/health", timeout=5)
d = r.json()
check("GET /health returns 200", r.status_code == 200)
check("health.status = healthy", d.get("status") == "healthy")
check("all 3 regions in health", len(d.get("regions", {})) == 3)

# 2. Carbon
r = httpx.get(f"{BASE}/carbon", timeout=5)
d = r.json()
check("GET /carbon returns 200", r.status_code == 200)
regions_in_response = {reg["region"] for reg in d.get("regions", [])}
check("us-east-1 in /carbon", "us-east-1" in regions_in_response)
check("eu-north-1 in /carbon", "eu-north-1" in regions_in_response)
check("ap-south-1 in /carbon", "ap-south-1" in regions_in_response)

# 3. Decision — default: EU should win
r = httpx.get(f"{BASE}/decision", timeout=5)
d = r.json()
check("GET /decision returns 200", r.status_code == 200)
check("default decision = eu-north-1", d.get("selected_region") == "eu-north-1", f"got {d.get('selected_region')}")
check("decision intensity = 70", d.get("carbon_intensity") == 70.0, f"got {d.get('carbon_intensity')}")
check("reason is non-empty", bool(d.get("reason")))

# 4. Proxy POST
r = httpx.post(f"{BASE}/proxy/api/task", json={"task":"test"}, timeout=10)
check("POST /proxy/api/task returns 200", r.status_code == 200, f"got {r.status_code}")
check("X-Eco-Router-Region header present", "X-Eco-Router-Region" in r.headers)
check("X-Carbon-Intensity header present", "X-Carbon-Intensity" in r.headers)
check("X-Request-Id header present", "X-Request-Id" in r.headers)
check("routed to eu-north-1", r.headers.get("X-Eco-Router-Region") == "eu-north-1",
      f"got {r.headers.get('X-Eco-Router-Region')}")
body = r.json()
check("response body contains region", body.get("region") == "eu-north-1")
check("response body simulated=true", body.get("simulated") == True)

# 5. Override carbon -> US becomes lowest
r2 = httpx.post(f"{BASE}/demo/carbon?region=us-east-1&intensity=30", timeout=5)
check("POST /demo/carbon returns 200", r2.status_code == 200)
time.sleep(0.3)
r3 = httpx.get(f"{BASE}/decision", timeout=5)
d3 = r3.json()
check("after override: decision = us-east-1", d3.get("selected_region") == "us-east-1",
      f"got {d3.get('selected_region')}")

# 6. Failover: mark EU unavailable
httpx.post(f"{BASE}/demo/carbon?region=us-east-1&intensity=340", timeout=5)
httpx.post(f"{BASE}/demo/health?region=eu-north-1&status=unavailable", timeout=5)
time.sleep(0.3)
r4 = httpx.get(f"{BASE}/decision", timeout=5)
d4 = r4.json()
check("failover: EU unavailable -> AP selected", d4.get("selected_region") == "ap-south-1",
      f"got {d4.get('selected_region')}")
check("eu-north-1 in unavailable_regions", "eu-north-1" in d4.get("unavailable_regions", []))

# Restore
httpx.post(f"{BASE}/demo/health?region=eu-north-1&status=available", timeout=5)

# 7. Metrics
r5 = httpx.get(f"{BASE}/metrics", timeout=5)
d5 = r5.json()
check("GET /metrics returns 200", r5.status_code == 200)
check("metrics.total_requests > 0", d5.get("total_requests", 0) > 0)
check("savings_label = ESTIMATED", "ESTIMATED" in d5.get("savings_label", ""))

# 8. History
r6 = httpx.get(f"{BASE}/history", timeout=5)
check("GET /history returns list", isinstance(r6.json(), list))

# 9. SSRF: target= param should NOT control routing
r7 = httpx.get(f"{BASE}/proxy/api/task?target=http://evil.internal", timeout=10)
check("SSRF: target= param does not change routing", r7.headers.get("X-Eco-Router-Region") is not None)

print(f"\n=== RESULTS: {len(PASS)}/{len(PASS)+len(FAIL)} PASSED ===")
if FAIL:
    print(f"FAILED: {FAIL}")
else:
    print("ALL TESTS PASSED!")
