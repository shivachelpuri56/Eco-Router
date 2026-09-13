"""
eco_router/cloud/aws_provider.py — AWS cloud region provider (stub).

IMPORTANT SECURITY NOTES:
- AWS credentials are NEVER hardcoded here or anywhere in the codebase
- This provider is only activated when REGION_PROVIDER=aws AND credentials exist
- If credentials are missing, get_provider() in __init__.py falls back to mock
- AWS credentials are read ONLY from environment / IAM role — never from config files
- This provider returns metadata ONLY — never exposes target URLs to clients

Phase H stub: returns the three Eco-Router simulated regions as AWS-labelled entries.
Future: integrate with boto3 to discover real EC2/ECS regions.

Required environment variables (if REGION_PROVIDER=aws):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION   (or AWS_REGION)

Optional:
    AWS_SESSION_TOKEN    (for assumed roles)
"""
from __future__ import annotations
import os

from .models import CloudRegion
from .provider import CloudRegionProvider


# AWS region metadata matching the three simulated Eco-Router regions
_AWS_REGIONS: list[CloudRegion] = [
    CloudRegion(
        id="us-east-1",
        provider="aws",
        display_name="US East (N. Virginia)",
        latitude=37.43,
        longitude=-79.00,
        electricity_maps_zone="US-MIDA-PJM",
        available=True,
        metadata={
            "aws_region_code": "us-east-1",
            "aws_partition": "aws",
            "note": "Phase H stub — real availability via boto3 in production",
        },
    ),
    CloudRegion(
        id="eu-north-1",
        provider="aws",
        display_name="EU North (Stockholm)",
        latitude=59.33,
        longitude=18.07,
        electricity_maps_zone="SE",
        available=True,
        metadata={
            "aws_region_code": "eu-north-1",
            "aws_partition": "aws",
            "note": "Phase H stub",
        },
    ),
    CloudRegion(
        id="ap-south-1",
        provider="aws",
        display_name="Asia Pacific (Mumbai)",
        latitude=19.08,
        longitude=72.88,
        electricity_maps_zone="IN-SO",
        available=True,
        metadata={
            "aws_region_code": "ap-south-1",
            "aws_partition": "aws",
            "note": "Phase H stub",
        },
    ),
]

_REGION_MAP: dict[str, CloudRegion] = {r.id: r for r in _AWS_REGIONS}


class AWSCloudRegionProvider(CloudRegionProvider):
    """
    AWS cloud region provider.

    Phase H: returns static metadata matching existing simulated regions.
    Production upgrade path: integrate boto3.client('ec2').describe_regions()
    to dynamically discover available AWS regions.

    SECURITY: Never returns credentials, endpoint URLs, or private network info.
    """

    @property
    def name(self) -> str:
        return "aws"

    def is_available(self) -> bool:
        """
        Returns True only when AWS credentials are present in the environment.
        Does NOT validate credentials — that requires a network call.
        """
        has_key_id = bool(os.environ.get("AWS_ACCESS_KEY_ID", "").strip())
        has_secret = bool(os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip())
        has_region = bool(
            os.environ.get("AWS_DEFAULT_REGION", "").strip()
            or os.environ.get("AWS_REGION", "").strip()
        )
        return has_key_id and has_secret and has_region

    def list_regions(self) -> list[CloudRegion]:
        """
        Return AWS region list.
        Phase H: static list matching simulated regions.
        Production: would call boto3 to discover real regions.
        """
        return list(_AWS_REGIONS)

    def get_region(self, region_id: str) -> CloudRegion | None:
        return _REGION_MAP.get(region_id)
