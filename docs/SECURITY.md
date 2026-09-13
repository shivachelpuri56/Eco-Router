# Security — Eco-Router

## SSRF Protection

**Server-Side Request Forgery (SSRF)** protection is mandatory in any reverse proxy.

### Implementation

All upstream URLs are determined **exclusively** by Eco-Router's region configuration. The client **cannot** specify a target URL.

```python
# eco_router/config.py
@property
def allowed_target_urls(self) -> frozenset[str]:
    return frozenset(r["url"] for r in DEFAULT_REGIONS.values())
# → {"http://localhost:9001", "http://localhost:9002", "http://localhost:9003"}
```

The proxy validates the target before every request:
```python
if target_base not in settings.allowed_target_urls:
    raise HTTPException(status_code=500, detail="Internal routing error")
```

**Tested:** SSRF protection is verified in the integration test suite.

## API Key Security

| Rule | Implementation |
|---|---|
| Never hardcoded | All keys in `.env`, loaded via pydantic-settings |
| Never logged | Loguru sink includes secret-pattern filter |
| Never in URLs | API keys passed as headers only |
| Never in frontend | Keys are server-side only; dashboard uses same-origin fetch |
| `.env` gitignored | Verified in `.gitignore` |

### API Key Requirements

If you enable Electricity Maps:
```
SERVICE:   Electricity Maps
KEY NAME:  ELECTRICITY_MAPS_API_KEY
WHERE:     https://api.electricitymap.org
HOW USED:  "auth-token" header — never in URL, never logged
```

## Header Safety

Hop-by-hop headers are stripped before forwarding to prevent proxy misuse:
```
connection, keep-alive, proxy-authenticate, proxy-authorization,
te, trailers, transfer-encoding, upgrade, host, content-length
```

## Request Body Limits

Default: 10 MB (`MAX_REQUEST_BODY_SIZE=10485760`)

Requests exceeding this limit receive HTTP 413 before upstream forwarding.

## Timeouts

All upstream requests enforce `REQUEST_TIMEOUT` (default 10 s).
Timeouts return HTTP 504 to the client — never hang indefinitely.

## Prototype Limitations

This is a development prototype. Production hardening would require:
- Authentication on proxy endpoints
- Rate limiting
- TLS/HTTPS
- Network-level isolation of region servers
- Secrets management (HashiCorp Vault, cloud secret managers)
- Dependency scanning in CI (pip-audit)

## Security Audit

Run a basic dependency audit:
```bash
pip-audit
```
