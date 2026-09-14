"""
test_cloud.py — Unit tests for Phase H cloud region abstraction.

Tests:
  - MockCloudRegionProvider returns correct regions
  - AWSCloudRegionProvider.is_available() detects missing credentials
  - get_provider() falls back to mock when AWS credentials absent
  - CloudRegion.to_api_dict() never exposes credentials/endpoints
  - Provider returns 3 regions matching existing simulated regions
  - Invalid region_id returns None
  - Provider name matches expected value
"""
import os
import pytest


class TestCloudRegionModel:
    def test_to_api_dict_structure(self):
        from eco_router.cloud.models import CloudRegion
        r = CloudRegion(
            id="us-east-1",
            provider="mock",
            display_name="US East",
            latitude=37.43,
            longitude=-79.00,
            electricity_maps_zone="US-MIDA-PJM",
            available=True,
            metadata={"simulated": True, "endpoint": "http://internal:9001", "secret": "abc"},
        )
        d = r.to_api_dict()
        assert d["id"] == "us-east-1"
        assert d["provider"] == "mock"
        assert d["display_name"] == "US East"
        assert d["available"] is True
        # Security: sensitive keys must NOT appear in API output
        assert "endpoint" not in d["metadata"]
        assert "secret" not in d["metadata"]
        # Non-sensitive keys pass through
        assert d["metadata"].get("simulated") is True

    def test_to_api_dict_has_coordinates(self):
        from eco_router.cloud.models import CloudRegion
        r = CloudRegion("eu-north-1", "mock", "EU North", 59.33, 18.07)
        d = r.to_api_dict()
        assert d["latitude"] == 59.33
        assert d["longitude"] == 18.07


class TestMockCloudProvider:
    def test_name(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        p = MockCloudRegionProvider()
        assert p.name == "mock"

    def test_is_always_available(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        p = MockCloudRegionProvider()
        assert p.is_available() is True

    def test_returns_three_regions(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        p = MockCloudRegionProvider()
        regions = p.list_regions()
        assert len(regions) == 3
        ids = {r.id for r in regions}
        assert "us-east-1" in ids
        assert "eu-north-1" in ids
        assert "ap-south-1" in ids

    def test_get_region_known(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        p = MockCloudRegionProvider()
        r = p.get_region("eu-north-1")
        assert r is not None
        assert r.id == "eu-north-1"
        assert r.provider == "mock"

    def test_get_region_unknown_returns_none(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        p = MockCloudRegionProvider()
        assert p.get_region("xx-invalid-99") is None

    def test_all_regions_have_coordinates(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        for r in MockCloudRegionProvider().list_regions():
            assert r.latitude != 0
            assert r.longitude != 0

    def test_to_api_response_structure(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        resp = MockCloudRegionProvider().to_api_response()
        assert resp["provider"] == "mock"
        assert resp["count"] == 3
        assert isinstance(resp["regions"], list)

    def test_api_response_no_internal_urls(self):
        from eco_router.cloud.mock_provider import MockCloudRegionProvider
        resp = MockCloudRegionProvider().to_api_response()
        for region_dict in resp["regions"]:
            # Endpoint URLs must not appear in API output
            assert "endpoint" not in region_dict
            assert "url" not in region_dict
            meta = region_dict.get("metadata", {})
            assert "endpoint" not in meta
            assert "url" not in meta


class TestAWSCloudProvider:
    def test_name(self):
        from eco_router.cloud.aws_provider import AWSCloudRegionProvider
        p = AWSCloudRegionProvider()
        assert p.name == "aws"

    def test_not_available_without_credentials(self, monkeypatch):
        from eco_router.cloud.aws_provider import AWSCloudRegionProvider
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        p = AWSCloudRegionProvider()
        assert p.is_available() is False

    def test_available_with_credentials(self, monkeypatch):
        from eco_router.cloud.aws_provider import AWSCloudRegionProvider
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        p = AWSCloudRegionProvider()
        assert p.is_available() is True

    def test_returns_three_regions(self):
        from eco_router.cloud.aws_provider import AWSCloudRegionProvider
        p = AWSCloudRegionProvider()
        assert len(p.list_regions()) == 3

    def test_region_provider_label_is_aws(self):
        from eco_router.cloud.aws_provider import AWSCloudRegionProvider
        for r in AWSCloudRegionProvider().list_regions():
            assert r.provider == "aws"


class TestProviderFactory:
    def test_get_provider_returns_mock_by_default(self, monkeypatch):
        monkeypatch.setattr("eco_router.config.settings.region_provider", "mock")
        from eco_router.cloud import get_provider
        p = get_provider()
        assert p.name == "mock"

    def test_get_provider_falls_back_to_mock_when_aws_no_creds(self, monkeypatch):
        monkeypatch.setattr("eco_router.config.settings.region_provider", "aws")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        from eco_router.cloud import get_provider
        p = get_provider()
        # Should fall back to mock
        assert p.name == "mock"

    def test_get_provider_unknown_name_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setattr("eco_router.config.settings.region_provider", "gcp_future")
        from eco_router.cloud import get_provider
        p = get_provider()
        assert p.name == "mock"

    def test_provider_is_always_usable_without_cloud_creds(self):
        """Critical: the app must start without any cloud credentials."""
        from eco_router.cloud import get_provider
        p = get_provider()
        regions = p.list_regions()
        assert len(regions) >= 1
        assert p.is_available() is True
