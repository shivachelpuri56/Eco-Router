"""
eco_router/cloud/__init__.py

Cloud Region Abstraction — Phase H

Provides a pluggable CloudRegionProvider interface so Eco-Router can work
with multiple cloud backends (mock for demos, AWS for production) without
changing core routing logic.

Architecture:
  CloudRegionProvider (abstract)
    ├── MockCloudRegionProvider  — local simulated regions, no credentials
    └── AWSCloudRegionProvider   — real AWS regions, key-gated

The routing engine continues to use server-side configuration for target URLs.
Clients cannot inject arbitrary targets (SSRF protection is preserved).

Usage:
    from eco_router.cloud import get_provider
    provider = get_provider()         # uses settings.region_provider
    regions  = provider.list_regions()
"""
from .provider import CloudRegionProvider
from .mock_provider import MockCloudRegionProvider
from .aws_provider import AWSCloudRegionProvider
from eco_router.config import settings


def get_provider() -> CloudRegionProvider:
    """
    Return the configured CloudRegionProvider.
    Falls back to mock if provider is unknown or credentials are missing.
    """
    name = settings.region_provider.lower()
    if name == "aws":
        provider = AWSCloudRegionProvider()
        if provider.is_available():
            return provider
        # Fall through to mock if AWS credentials are absent
        import logging
        logging.getLogger(__name__).warning(
            "REGION_PROVIDER=aws but AWS credentials not available — "
            "falling back to mock provider"
        )
    return MockCloudRegionProvider()


__all__ = [
    "CloudRegionProvider",
    "MockCloudRegionProvider",
    "AWSCloudRegionProvider",
    "get_provider",
]
