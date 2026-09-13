# Eco-Router — Cloud Region Abstraction

## Architecture

`
CloudRegionProvider (abstract)
  |-- MockCloudRegionProvider   (default, no credentials)
  |-- AWSCloudRegionProvider    (requires AWS credentials)
`

## Configuration

Set in .env:

`
REGION_PROVIDER=mock    # default — no credentials needed
# REGION_PROVIDER=aws   # enable AWS provider
`

For AWS provider:

`
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=
`

> If AWS credentials are absent, the system automatically falls back to mock.

## API Endpoints

### GET /cloud/regions

Returns safe metadata for all configured regions.

`json
{
  "provider": "mock",
  "count": 3,
  "regions": [
    {
      "id": "us-east-1",
      "provider": "mock",
      "display_name": "US East (N. Virginia)",
      "latitude": 37.43,
      "longitude": -79.0,
      "electricity_maps_zone": "US-MIDA-PJM",
      "available": true,
      "metadata": { "simulated": true }
    }
  ]
}
`

### GET /cloud/regions/{region_id}

Returns metadata for a single region, or 404 if not found.

## Security

- Credentials are NEVER returned in API responses
- Internal target URLs are NEVER exposed to clients (SSRF protection)
- Sensitive metadata keys (endpoint, url, secret, key, token, password) are filtered
- AWS credentials are read from environment variables only
- The routing engine obtains target URLs from server-side config only

## Current Simulated Regions

| Region | Location | Typical Carbon Intensity |
|---|---|---|
| us-east-1 | Virginia, USA | ~340 gCO2e/kWh (mock) |
| eu-north-1 | Stockholm, Sweden | ~70 gCO2e/kWh (mock) |
| ap-south-1 | Mumbai, India | ~180 gCO2e/kWh (mock) |

All values are simulated. Not real measurements.

## Production Upgrade Path

Phase H (current): Static metadata, same 3 simulated regions.
Future: Integrate boto3 to discover real AWS regions dynamically.
