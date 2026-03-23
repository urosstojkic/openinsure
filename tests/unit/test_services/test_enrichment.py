"""Tests for the data enrichment service."""

from __future__ import annotations

import pytest

from openinsure.services.enrichment import (
    BreachHistoryProvider,
    FirmographicsProvider,
    SecurityRatingProvider,
    enrich_submission,
)


@pytest.fixture
def sample_submission() -> dict:
    return {
        "id": "sub-enrich-test",
        "applicant_name": "Test Corp",
        "risk_data": {
            "annual_revenue": 5_000_000,
            "employee_count": 50,
            "industry_sic_code": "7372",
            "has_mfa": True,
            "has_endpoint_protection": True,
            "prior_incidents": 0,
        },
    }


@pytest.mark.asyncio
class TestEnrichmentProviders:
    async def test_security_rating_returns_score(self, sample_submission: dict) -> None:
        provider = SecurityRatingProvider()
        result = await provider.enrich(sample_submission)
        assert result["provider"] == "security_rating"
        assert "data" in result
        assert "overall_score" in result["data"]
        assert 0 <= result["data"]["overall_score"] <= 950

    async def test_firmographics_returns_data(self, sample_submission: dict) -> None:
        provider = FirmographicsProvider()
        result = await provider.enrich(sample_submission)
        assert result["provider"] == "firmographics"
        assert "verified_revenue" in result["data"]
        assert "credit_rating" in result["data"]

    async def test_breach_history_returns_data(self, sample_submission: dict) -> None:
        provider = BreachHistoryProvider()
        result = await provider.enrich(sample_submission)
        assert result["provider"] == "breach_history"
        assert "total_known_breaches" in result["data"]

    async def test_enrichment_deterministic(self, sample_submission: dict) -> None:
        """Same submission produces same enrichment results (seeded RNG)."""
        r1 = await enrich_submission(sample_submission)
        r2 = await enrich_submission(sample_submission)
        assert r1["risk_summary"]["composite_risk_score"] == r2["risk_summary"]["composite_risk_score"]


@pytest.mark.asyncio
class TestEnrichSubmission:
    async def test_returns_all_providers(self, sample_submission: dict) -> None:
        result = await enrich_submission(sample_submission)
        assert "enrichment_data" in result
        assert "risk_summary" in result
        assert "security_rating" in result["enrichment_data"]
        assert "firmographics" in result["enrichment_data"]
        assert "breach_history" in result["enrichment_data"]

    async def test_composite_risk_score_range(self, sample_submission: dict) -> None:
        result = await enrich_submission(sample_submission)
        score = result["risk_summary"]["composite_risk_score"]
        assert 0 <= score <= 1.0

    async def test_enriched_at_timestamp(self, sample_submission: dict) -> None:
        result = await enrich_submission(sample_submission)
        assert "enriched_at" in result["risk_summary"]
