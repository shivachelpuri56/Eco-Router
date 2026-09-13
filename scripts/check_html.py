import httpx
r = httpx.get("http://localhost:8000/", timeout=5)
html = r.text
print("HTTP status:", r.status_code)
print("Content-Length:", len(html), "bytes")
print()

banned = ["1M1B", "IBM SkillsBuild", "AICTE", "Virtual Internship", "SkillsBuild"]
print("-- Banned branding --")
all_clean = True
for term in banned:
    found = term in html
    if found: all_clean = False
    print(f"  [{('FAIL' if found else 'OK')}] {term!r}")
print("  => " + ("All clean!" if all_clean else "VIOLATIONS FOUND"))

print()
print("-- Key features --")
features = [
    ("Why This Region",    "Why This Region" in html),
    ("System Status",      "System Status" in html),
    ("Demo Mode label",    "Demo Mode" in html),
    ("source-mock class",  "source-mock" in html),
    ("source-live class",  "source-live" in html),
    ("SDG 13",             "SDG 13" in html),
    ("skip-link",          "skip-link" in html),
    ("ESTIMATED",          "ESTIMATED" in html),
    ("simulated",          "simulated" in html.lower()),
    ("aria-label",         "aria-label" in html),
    ("Title correct",      "Eco-Router \u2014 Carbon-Aware Intelligent Load Balancer" in html),
    ("No hardcoded LIVE",  ">Live<" not in html and "badge-green" not in html),
    ("SDG Climate Action", "Climate Action" in html),
    ("Footer clean",       ("1M1B" not in html) and ("AICTE" not in html)),
]
for name, ok in features:
    print(f"  [{'OK' if ok else 'MISS'}] {name}")
