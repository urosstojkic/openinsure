"""Tests for SubmissionService — core triage, quote, and bind logic.

Uses InMemory repositories (no mocking of factory needed — just instantiate
the repo directly and patch the service).
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_submission(**overrides: Any) -> dict[str, Any]:
    """Build a minimal submission dict for testing."""
    data: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "channel": "email",
        "line_of_business": "cyber",
        "status": "received",
        "applicant_name": "Acme Cyber Corp",
        "insured_name": "Acme Cyber Corp",
        "requested_effective_date": "2025-07-01",
        "requested_expiration_date": "2026-07-01",
        "cyber_risk_data": json.dumps(
            {
                "annual_revenue": 5000000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 3.5,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "prior_incidents": 0,
            }
        ),
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


@pytest.fixture
def submission_repo():
    """Create an InMemory submission repository."""
    from openinsure.infrastructure.repositories.submissions import InMemorySubmissionRepository

    return InMemorySubmissionRepository()


@pytest.fixture
def policy_repo():
    """Create an InMemory policy repository."""
    from openinsure.infrastructure.repositories.policies import InMemoryPolicyRepository

    return InMemoryPolicyRepository()


@pytest.fixture
def billing_repo():
    """Create an InMemory billing repository."""
    from openinsure.infrastructure.repositories.billing import InMemoryBillingRepository

    return InMemoryBillingRepository()


@pytest.fixture
def service(submission_repo, policy_repo, billing_repo):
    """Create a SubmissionService with injected repositories."""
    from openinsure.services.submission_service import SubmissionService

    svc = SubmissionService()
    svc._repo = submission_repo  # noqa: SLF001
    return svc


class TestSubmissionServiceTriage:
    """Tests for the triage flow."""

    @pytest.mark.asyncio
    async def test_triage_local_fallback_basic(self, service, submission_repo):
        """Test triage with local fallback (Foundry unavailable)."""
        sub = _make_submission()
        await submission_repo.create(sub)

        # Patch Foundry to be unavailable
        with patch("openinsure.services.submission_service.get_submission_repository", return_value=submission_repo):
            result = await service.run_triage(sub["id"], sub)

        assert result["status"] == "underwriting"
        assert isinstance(result["risk_score"], (int, float))
        assert result["recommendation"] in ("proceed_to_quote", "refer", "decline")
        assert isinstance(result["flags"], list)

    @pytest.mark.asyncio
    async def test_triage_high_risk_incidents(self, service, submission_repo):
        """Submissions with high prior incidents should be declined or referred."""
        sub = _make_submission(
            cyber_risk_data=json.dumps(
                {
                    "annual_revenue": 5000000,
                    "employee_count": 50,
                    "industry_sic_code": "7372",
                    "security_maturity_score": 3.5,
                    "has_mfa": True,
                    "has_endpoint_protection": True,
                    "has_backup_strategy": True,
                    "prior_incidents": 10,
                }
            ),
        )
        await submission_repo.create(sub)

        result = await service.run_triage(sub["id"], sub)

        assert result["status"] == "underwriting"
        # High incidents should trigger referral or decline
        assert result["risk_score"] >= 7


class TestSubmissionServiceQuote:
    """Tests for the quote generation flow."""

    @pytest.mark.asyncio
    async def test_generate_quote_local_fallback(self, service, submission_repo):
        """Test quote generation with Foundry unavailable (local rating engine)."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps({"risk_score": 5, "recommendation": "proceed_to_quote"}),
        )
        await submission_repo.create(sub)

        with (
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
        ):
            result = await service.generate_quote(
                sub["id"],
                sub,
                user_role="underwriter",
                user_display_name="Test User",
            )

        assert "premium" in result or "escalated" in result
        if not result.get("escalated"):
            assert result["premium"] > 0

    @pytest.mark.asyncio
    async def test_generate_quote_no_risk_data(self, service, submission_repo):
        """Quote generation with minimal risk data should still produce a result."""
        sub = _make_submission(
            status="underwriting",
            cyber_risk_data="{}",
            triage_result=json.dumps({"risk_score": 5}),
        )
        await submission_repo.create(sub)

        with (
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
        ):
            result = await service.generate_quote(
                sub["id"],
                sub,
                user_role="underwriter",
                user_display_name="Test User",
            )

        # Should still produce a premium (using defaults)
        assert "premium" in result or "escalated" in result


class TestSubmissionServiceHelpers:
    """Tests for internal helper functions."""

    def test_safe_float_valid(self):
        from openinsure.services.submission_service import _safe_float

        assert _safe_float(42, 0.0) == 42.0
        assert _safe_float("3.14", 0.0) == 3.14
        assert _safe_float(0, 1.0) == 0.0

    def test_safe_float_invalid(self):
        from openinsure.services.submission_service import _safe_float

        assert _safe_float(None, 5.0) == 5.0
        assert _safe_float("not-a-number", 5.0) == 5.0
        assert _safe_float([], 5.0) == 5.0

    def test_safe_float_nan(self):
        from openinsure.services.submission_service import _safe_float

        assert _safe_float(float("nan"), 5.0) == 5.0

    def test_parse_json_field_dict(self):
        from openinsure.services.submission_service import _parse_json_field

        assert _parse_json_field({"key": "val"}) == {"key": "val"}

    def test_parse_json_field_string(self):
        from openinsure.services.submission_service import _parse_json_field

        assert _parse_json_field('{"key": "val"}') == {"key": "val"}

    def test_parse_json_field_invalid(self):
        from openinsure.services.submission_service import _parse_json_field

        assert _parse_json_field("not-json") == {}
        assert _parse_json_field(None) == {}
        assert _parse_json_field(42) == {}

    def test_extract_risk_data(self):
        from openinsure.services.submission_service import _extract_risk_data

        record = {"cyber_risk_data": json.dumps({"annual_revenue": 5000000})}
        result = _extract_risk_data(record)
        assert result["annual_revenue"] == 5000000

    def test_extract_risk_data_empty(self):
        from openinsure.services.submission_service import _extract_risk_data

        assert _extract_risk_data({}) == {}

    def test_build_rating_input(self):
        from openinsure.services.submission_service import _build_rating_input

        risk_data = {
            "annual_revenue": 1000000,
            "employee_count": 25,
            "industry_sic_code": "7372",
            "security_maturity_score": 4.0,
            "has_mfa": True,
            "has_endpoint_protection": True,
            "has_backup_strategy": True,
            "prior_incidents": 1,
        }
        rating_input = _build_rating_input(risk_data)
        assert rating_input.employee_count == 25
        assert rating_input.has_mfa is True
        assert rating_input.prior_incidents == 1
