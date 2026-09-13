"""
Configuration management for Eco-Router.
All settings are loaded from environment variables / .env file.
API keys are NEVER hardcoded.
"""
from __future__ import annotations
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Simulated Cloud Region Configuration ─────────────────────────────────────
# These represent hypothetical cloud regions running as local mock servers.
# NOT actual AWS, GCP, or Azure infrastructure.
DEFAULT_REGIONS: dict[str, dict[str, Any]] = {
    "us-east-1": {
        "url": "http://localhost:9001",
        "name": "US East (N. Virginia)",
        "electricity_maps_zone": "US-MIDA-PJM",
    },
    "eu-north-1": {
        "url": "http://localhost:9002",
        "name": "EU North (Stockholm)",
        "electricity_maps_zone": "SE",
    },
    "ap-south-1": {
        "url": "http://localhost:9003",
        "name": "Asia Pacific (Mumbai)",
        "electricity_maps_zone": "IN-SO",
    },
}

# Headers that MUST NOT be forwarded to upstream (RFC 7230 hop-by-hop)
HOP_BY_HOP_HEADERS: frozenset[str] = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",           # rewritten to target host
    "content-length", # httpx recalculates this
})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    app_version: str = "1.0.0"

    # ── Carbon Provider ───────────────────────────────────────────────────────
    # Options: mock | electricity_maps | carbon_aware_sdk
    carbon_provider: str = "mock"
    carbon_cache_ttl: int = 300         # seconds until data is stale
    carbon_update_interval: int = 60    # background refresh interval (s)

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./eco_router.db"

    # ── Request Settings ──────────────────────────────────────────────────────
    request_timeout: float = 10.0
    max_request_body_size: int = 10 * 1024 * 1024  # 10 MB

    # ── Health Checks ─────────────────────────────────────────────────────────
    health_check_interval: int = 30  # seconds

    # ── Carbon Savings Estimation ─────────────────────────────────────────────
    # ESTIMATED energy per proxied request — configurable assumption.
    # All savings derived from this are labelled ESTIMATED.
    energy_per_request_kwh: float = 0.0001

    # ── Optional API Keys — loaded from env, never hardcoded ──────────────────
    electricity_maps_api_key: str = ""
    carbon_aware_sdk_url: str = ""
    gemini_api_key: str = ""  # optional — enables AI-powered insights if set
    gemini_model: str = "gemini-2.0-flash"  # configurable model name
    
    # ── Authentication ──────────────────────────────────────────────────────────
    auth_secret: str = "DEV_SECRET_CHANGE_ME_IN_PRODUCTION_92a3f8"
    auth_algorithm: str = "HS256"
    auth_token_expire_minutes: int = 1440  # 24 hours

    # ── Cloud Region Provider ──────────────────────────────────────────────────
    # Options: mock | aws
    # 'mock' works without any cloud credentials — safe for demos.
    # 'aws' requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION
    region_provider: str = "mock"

    # ── Mock Carbon Values — configurable for demo scenarios ──────────────────
    # Scenario A (default): EU is greenest
    # Scenario B: change AP to 50 → AP becomes greenest
    # Scenario C: change US to 30 → US becomes greenest
    mock_carbon_us_east_1: float = 340.0
    mock_carbon_eu_north_1: float = 70.0
    mock_carbon_ap_south_1: float = 180.0

    @property
    def regions(self) -> dict[str, dict[str, Any]]:
        """All configured simulated regions."""
        return DEFAULT_REGIONS

    @property
    def mock_carbon_values(self) -> dict[str, float]:
        """Current mock carbon intensity values per region (gCO₂e/kWh)."""
        return {
            "us-east-1":  self.mock_carbon_us_east_1,
            "eu-north-1": self.mock_carbon_eu_north_1,
            "ap-south-1": self.mock_carbon_ap_south_1,
        }

    @property
    def allowed_target_urls(self) -> frozenset[str]:
        """
        SSRF protection: the only URLs Eco-Router may ever connect to.
        Clients CANNOT override this list.
        """
        return frozenset(r["url"] for r in DEFAULT_REGIONS.values())


# Single shared settings instance
settings = Settings()
