"""Tests for SubmissionService — core triage, quote, and bind logic.

Uses InMemory repositories (no mocking of factory needed — just instantiate
the repo directly and patch the service).
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
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


class TestSubmissionServiceTriageFoundry:
    """Tests for triage with Foundry agent available."""

    @pytest.mark.asyncio
    async def test_run_triage_foundry_success(self, service, submission_repo):
        """Foundry returns risk_score -> status transitions to underwriting."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(return_value={
            "response": {
                "risk_score": 5,
                "appetite_match": "yes",
                "confidence": 0.85,
                "reasoning": "Low risk commercial cyber",
            },
            "source": "foundry",
            "raw": '{"risk_score": 5}',
            "execution_time_ms": 150,
        })

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.agents.prompts.get_triage_context",
                new_callable=AsyncMock,
                return_value="Standard cyber appetite guidelines",
            ),
            patch(
                "openinsure.agents.prompts.build_triage_prompt",
                return_value="Triage this cyber submission",
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["status"] == "underwriting"
        assert result["risk_score"] == 5
        assert result["recommendation"] in ("proceed_to_quote", "refer")
        assert isinstance(result["flags"], list)
        mock_foundry.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_triage_foundry_decline(self, service, submission_repo):
        """Foundry returns appetite_match=no -> recommendation=decline."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(return_value={
            "response": {
                "risk_score": 9,
                "appetite_match": "no",
                "confidence": 0.92,
                "reasoning": "Outside appetite - high risk industry",
            },
            "source": "foundry",
            "raw": '{"risk_score": 9, "appetite_match": "no"}',
            "execution_time_ms": 120,
        })

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.agents.prompts.get_triage_context",
                new_callable=AsyncMock,
                return_value="Standard cyber appetite guidelines",
            ),
            patch(
                "openinsure.agents.prompts.build_triage_prompt",
                return_value="Triage this cyber submission",
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["recommendation"] == "decline"
        mock_foundry.invoke.assert_called_once()


class TestSubmissionServiceQuoteFoundry:
    """Tests for quote generation with Foundry agent."""

    @pytest.mark.asyncio
    async def test_generate_quote_foundry_success(self, service, submission_repo):
        """Foundry UW agent returns recommended_premium -> premium set."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps(
                {"risk_score": 5, "recommendation": "proceed_to_quote"}
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(return_value={
            "response": {
                "recommended_premium": 15000,
                "confidence": 0.88,
                "reasoning": "Standard cyber risk - adequate controls",
                "coverages": [
                    {"type": "Cyber Liability", "limit": 1000000, "deductible": 10000}
                ],
            },
            "source": "foundry",
            "raw": '{"recommended_premium": 15000}',
            "execution_time_ms": 200,
        })

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.agents.prompts.build_underwriting_prompt",
                return_value="Underwrite this submission",
            ),
            patch(
                "openinsure.agents.prompts.get_triage_context",
                new_callable=AsyncMock,
                return_value="UW guidelines",
            ),
            patch(
                "openinsure.agents.prompts._get_rating_breakdown",
                return_value={"base_premium": 10000, "factors": {}},
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(
                        decision="auto_execute", reason="Within auto limit"
                    ),
                },
            ),
        ):
            result = await service.generate_quote(
                sub["id"],
                sub,
                user_role="underwriter",
                user_display_name="Test UW",
            )

        assert result.get("escalated") is False
        assert result["premium"] == 15000
        mock_foundry.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_quote_authority_escalation(self, service, submission_repo):
        """Premium exceeds authority -> escalated=True."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps(
                {"risk_score": 5, "recommendation": "proceed_to_quote"}
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(return_value={
            "response": {
                "recommended_premium": 75000,
                "confidence": 0.80,
                "reasoning": "Large cyber program - elevated risk",
            },
            "source": "foundry",
            "raw": '{"recommended_premium": 75000}',
            "execution_time_ms": 250,
        })

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.agents.prompts.build_underwriting_prompt",
                return_value="Underwrite this submission",
            ),
            patch(
                "openinsure.agents.prompts.get_triage_context",
                new_callable=AsyncMock,
                return_value="UW guidelines",
            ),
            patch(
                "openinsure.agents.prompts._get_rating_breakdown",
                return_value=None,
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": True,
                    "auth_result": MagicMock(decision="escalate"),
                    "escalation_id": "esc-quote-001",
                },
            ),
        ):
            result = await service.generate_quote(
                sub["id"],
                sub,
                user_role="underwriter_analyst",
                user_display_name="Junior UW",
            )

        assert result["escalated"] is True
        assert "escalation_id" in result


class TestSubmissionServiceBind:
    """Tests for the bind flow."""

    @pytest.mark.asyncio
    async def test_bind_creates_policy(self, service, submission_repo):
        """Bind creates policy + billing."""
        sub = _make_submission(
            status="quoted",
            quoted_premium=15000,
            triage_result=json.dumps(
                {"risk_score": 5, "recommendation": "proceed_to_quote"}
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(
                        decision="auto_execute", reason="Within bind limit"
                    ),
                },
            ),
            patch(
                "openinsure.services.bind_handlers.dispatch_bind_events",
                new_callable=AsyncMock,
                return_value={
                    "policy": {"id": "pol-001", "status": "active"},
                    "billing": {"status": "created"},
                    "reinsurance": None,
                },
            ),
            patch(
                "openinsure.services.submission_service._auto_cession",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
            patch(
                "openinsure.infrastructure.factory.get_policy_repository",
                return_value=MagicMock(),
            ),
            patch(
                "openinsure.api.billing.create_billing_account_on_bind",
                new_callable=AsyncMock,
            ),
        ):
            result = await service.bind(
                sub["id"],
                sub,
                user_role="underwriter",
                user_display_name="Test UW",
            )

        assert result.get("escalated") is False
        assert "policy_id" in result
        assert "policy_number" in result
        assert result["premium"] == 15000

    @pytest.mark.asyncio
    async def test_bind_already_bound(self, service, submission_repo):
        """Binding from a terminal state (declined) raises InvalidTransitionError."""
        from openinsure.domain.state_machine import InvalidTransitionError

        sub = _make_submission(status="declined")
        await submission_repo.create(sub)

        with (
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute"),
                },
            ),
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=MagicMock(is_available=False),
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
            patch(
                "openinsure.services.submission_service.get_policy_repository",
                return_value=MagicMock(),
            ),
            patch(
                "openinsure.api.billing.create_billing_account_on_bind",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(InvalidTransitionError):
                await service.bind(
                    sub["id"],
                    sub,
                    user_role="underwriter",
                    user_display_name="Test UW",
                )

    @pytest.mark.asyncio
    async def test_bind_wrong_status(self, service, submission_repo):
        """Binding from received status (not quoted) raises error."""
        from openinsure.domain.state_machine import InvalidTransitionError

        sub = _make_submission(status="received")
        await submission_repo.create(sub)

        with (
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute"),
                },
            ),
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=MagicMock(is_available=False),
            ),
            patch(
                "openinsure.services.event_publisher.publish_domain_event",
                new_callable=AsyncMock,
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
            patch(
                "openinsure.services.submission_service.get_policy_repository",
                return_value=MagicMock(),
            ),
            patch(
                "openinsure.api.billing.create_billing_account_on_bind",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(InvalidTransitionError):
                await service.bind(
                    sub["id"],
                    sub,
                    user_role="underwriter",
                    user_display_name="Test UW",
                )


class TestSubmissionServiceCalculatePremium:
    """Tests for calculate_premium (backward compat alias)."""

    @pytest.mark.asyncio
    async def test_calculate_premium_local_rating_engine(self, service, submission_repo):
        """Rating engine calculates premium from risk data."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps(
                {"risk_score": 5, "recommendation": "proceed_to_quote"}
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
        ):
            result = await service.calculate_premium(sub["id"], sub)

        assert result["premium"] > 0
        assert result["ai_mode"] == "local_rating_engine"

    @pytest.mark.asyncio
    async def test_calculate_premium_lob_minimum_fallback(self, service, submission_repo):
        """When rating engine fails, uses LOB minimum premium."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps(
                {"risk_score": 5, "recommendation": "proceed_to_quote"}
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.services.submission_service._build_rating_input",
                side_effect=ValueError("Invalid risk data for rating"),
            ),
            patch(
                "openinsure.infrastructure.factory.get_database_adapter",
                return_value=None,
            ),
        ):
            result = await service.calculate_premium(sub["id"], sub)

        assert result["premium"] == 2500.0
        assert result["ai_mode"] == "lob_minimum_fallback"


# ---------------------------------------------------------------------------
# Tests for _check_authority_and_escalate
# ---------------------------------------------------------------------------


class TestCheckAuthorityAndEscalate:
    """Tests for the _check_authority_and_escalate helper function."""

    @pytest.mark.asyncio
    async def test_bind_action_with_custom_limit(self):
        """action='bind' calls check_bind_authority with provided limit."""
        from openinsure.services.submission_service import _check_authority_and_escalate

        result = await _check_authority_and_escalate(
            action="bind",
            premium=5000,
            user_role="underwriter",
            user_display_name="Test UW",
            entity_id="sub-1",
            limit=Decimal("2000000"),
        )
        assert result["escalated"] is False
        assert "auth_result" in result

    @pytest.mark.asyncio
    async def test_bind_action_default_limit(self):
        """action='bind' with no limit uses default 1000000."""
        from openinsure.services.submission_service import _check_authority_and_escalate

        result = await _check_authority_and_escalate(
            action="bind",
            premium=5000,
            user_role="underwriter",
            user_display_name="Test UW",
            entity_id="sub-1",
        )
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_quote_escalation_flow(self):
        """Quote action with ESCALATE decision calls escalation service."""
        from openinsure.rbac.authority import AuthorityDecision, AuthorityResult
        from openinsure.services.submission_service import _check_authority_and_escalate

        mock_auth_result = AuthorityResult(
            decision=AuthorityDecision.ESCALATE,
            reason="Premium exceeds analyst authority",
            required_role="senior_underwriter",
            escalation_chain=["senior_underwriter", "lob_head"],
        )

        with (
            patch(
                "openinsure.services.submission_service.AuthorityEngine",
                return_value=MagicMock(
                    check_quote_authority=MagicMock(return_value=mock_auth_result),
                ),
            ),
            patch(
                "openinsure.services.escalation.escalate",
                new_callable=AsyncMock,
                return_value={"id": "esc-test-001"},
            ) as mock_esc,
        ):
            result = await _check_authority_and_escalate(
                action="quote",
                premium=100000,
                user_role="uw_analyst",
                user_display_name="Junior UW",
                entity_id="sub-1",
            )

        assert result["escalated"] is True
        assert result["escalation_id"] == "esc-test-001"
        mock_esc.assert_called_once()

    @pytest.mark.asyncio
    async def test_bind_escalation_flow(self):
        """Bind action with ESCALATE decision triggers escalation."""
        from openinsure.rbac.authority import AuthorityDecision, AuthorityResult
        from openinsure.services.submission_service import _check_authority_and_escalate

        mock_auth_result = AuthorityResult(
            decision=AuthorityDecision.ESCALATE,
            reason="Bind authority exceeded",
            required_role="lob_head",
            escalation_chain=["lob_head", "cuo"],
        )

        with (
            patch(
                "openinsure.services.submission_service.AuthorityEngine",
                return_value=MagicMock(
                    check_bind_authority=MagicMock(return_value=mock_auth_result),
                ),
            ),
            patch(
                "openinsure.services.escalation.escalate",
                new_callable=AsyncMock,
                return_value={"id": "esc-bind-001"},
            ),
        ):
            result = await _check_authority_and_escalate(
                action="bind",
                premium=200000,
                user_role="uw_analyst",
                user_display_name="Junior UW",
                entity_id="sub-2",
                limit=Decimal("5000000"),
            )

        assert result["escalated"] is True
        assert result["escalation_id"] == "esc-bind-001"


# ---------------------------------------------------------------------------
# Tests for _auto_cession
# ---------------------------------------------------------------------------


class TestAutoCession:
    """Tests for the _auto_cession function."""

    @pytest.mark.asyncio
    async def test_no_active_treaties(self):
        """Returns early when no active treaties found."""
        from openinsure.services.submission_service import _auto_cession

        mock_treaty_repo = MagicMock()
        mock_treaty_repo.list_all = AsyncMock(return_value=[])

        with (
            patch("openinsure.infrastructure.factory.get_reinsurance_repository", return_value=mock_treaty_repo),
            patch("openinsure.infrastructure.factory.get_cession_repository", return_value=MagicMock()),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
        ):
            await _auto_cession("pol-1", "POL-2025-ABC", {"premium": 15000})

        mock_treaty_repo.list_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_applicable_cessions(self):
        """Returns early when calculate_cession returns empty list."""
        from openinsure.services.submission_service import _auto_cession

        raw_treaties = [
            {
                "id": "treaty-1",
                "treaty_number": "TR-001",
                "treaty_type": "quota_share",
                "reinsurer_name": "Swiss Re",
                "status": "active",
                "effective_date": "2025-01-01",
                "expiration_date": "2026-01-01",
            }
        ]

        mock_treaty_repo = MagicMock()
        mock_treaty_repo.list_all = AsyncMock(return_value=raw_treaties)
        mock_cession_repo = MagicMock()
        mock_cession_repo.create = AsyncMock()

        with (
            patch("openinsure.infrastructure.factory.get_reinsurance_repository", return_value=mock_treaty_repo),
            patch("openinsure.infrastructure.factory.get_cession_repository", return_value=mock_cession_repo),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch("openinsure.services.reinsurance.calculate_cession", return_value=[]),
            patch("openinsure.domain.reinsurance.ReinsuranceContract", return_value=MagicMock()),
        ):
            await _auto_cession("pol-1", "POL-2025-ABC", {"premium": 15000})

        mock_cession_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_cessions_without_db_adapter(self):
        """Creates cessions without transaction when no db adapter."""
        from openinsure.services.submission_service import _auto_cession

        raw_treaties = [
            {
                "id": "treaty-1",
                "treaty_number": "TR-001",
                "treaty_type": "quota_share",
                "reinsurer_name": "Swiss Re",
                "status": "active",
                "effective_date": "2025-01-01",
                "expiration_date": "2026-01-01",
                "lines_of_business": ["cyber"],
                "retention": 500000,
                "limit": 5000000,
                "rate": 25,
                "capacity_total": 10000000,
                "capacity_used": 0,
            }
        ]

        mock_treaty_repo = MagicMock()
        mock_treaty_repo.list_all = AsyncMock(return_value=raw_treaties)
        mock_cession_repo = MagicMock()
        mock_cession_repo.create = AsyncMock()

        mock_cession = MagicMock()
        mock_cession.treaty_id = "treaty-1"
        mock_cession.ceded_premium = Decimal("3750")
        mock_cession.ceded_limit = Decimal("250000")

        with (
            patch("openinsure.infrastructure.factory.get_reinsurance_repository", return_value=mock_treaty_repo),
            patch("openinsure.infrastructure.factory.get_cession_repository", return_value=mock_cession_repo),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch("openinsure.services.reinsurance.calculate_cession", return_value=[mock_cession]),
            patch("openinsure.domain.reinsurance.ReinsuranceContract", return_value=MagicMock()),
        ):
            await _auto_cession("pol-1", "POL-2025-ABC", {"premium": 15000})

        mock_cession_repo.create.assert_called_once()
        record = mock_cession_repo.create.call_args[0][0]
        assert record["treaty_id"] == "treaty-1"
        assert record["policy_id"] == "pol-1"
        assert record["ceded_premium"] == 3750.0

    @pytest.mark.asyncio
    async def test_cessions_with_db_adapter(self):
        """Creates cessions within transaction when db adapter present."""
        from openinsure.services.submission_service import _auto_cession

        raw_treaties = [
            {
                "id": "treaty-1",
                "treaty_number": "TR-001",
                "treaty_type": "quota_share",
                "reinsurer_name": "Swiss Re",
                "status": "active",
                "effective_date": "2025-01-01",
                "expiration_date": "2026-01-01",
                "capacity_used": 0,
            }
        ]

        mock_treaty_repo = MagicMock()
        mock_treaty_repo.list_all = AsyncMock(return_value=raw_treaties)
        mock_cession_repo = MagicMock()
        mock_cession_repo.create = AsyncMock()

        mock_cession = MagicMock()
        mock_cession.treaty_id = "treaty-1"
        mock_cession.ceded_premium = Decimal("3750")
        mock_cession.ceded_limit = Decimal("250000")

        mock_txn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_db = MagicMock()
        mock_db.transaction.return_value = mock_ctx

        with (
            patch("openinsure.infrastructure.factory.get_reinsurance_repository", return_value=mock_treaty_repo),
            patch("openinsure.infrastructure.factory.get_cession_repository", return_value=mock_cession_repo),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=mock_db),
            patch("openinsure.services.reinsurance.calculate_cession", return_value=[mock_cession]),
            patch("openinsure.domain.reinsurance.ReinsuranceContract", return_value=MagicMock()),
        ):
            await _auto_cession("pol-1", "POL-2025-ABC", {"premium": 15000})

        mock_cession_repo.create.assert_called_once()
        assert mock_cession_repo.create.call_args[1].get("txn") == mock_txn

    @pytest.mark.asyncio
    async def test_exception_handled_gracefully(self):
        """Exceptions in _auto_cession are caught and logged."""
        from openinsure.services.submission_service import _auto_cession

        with patch(
            "openinsure.infrastructure.factory.get_reinsurance_repository",
            side_effect=RuntimeError("DB unavailable"),
        ):
            # Should not raise
            await _auto_cession("pol-1", "POL-2025-ABC", {"premium": 15000})


# ---------------------------------------------------------------------------
# Tests for local triage fallback paths (knowledge store)
# ---------------------------------------------------------------------------


class TestSubmissionServiceTriageLocalFallback:
    """Tests for knowledge-store-driven local triage paths."""

    @pytest.mark.asyncio
    async def test_triage_appetite_rules_failed(self, service, submission_repo):
        """Relational appetite rules failure triggers referral."""
        sub = _make_submission(product_id="cyber-smb")
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_relations = MagicMock()
        mock_relations.check_appetite = AsyncMock(
            return_value=(False, ["sic_not_in_appetite"])
        )

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.infrastructure.factory.get_product_relations_repository",
                return_value=mock_relations,
            ),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["risk_score"] == 8
        assert "sic_not_in_appetite" in result["flags"]
        assert result["recommendation"] == "refer"

    @pytest.mark.asyncio
    async def test_triage_guidelines_security_below_minimum(self, service, submission_repo):
        """Knowledge store guidelines: security score below minimum."""
        sub = _make_submission(
            cyber_risk_data=json.dumps(
                {
                    "annual_revenue": 5000000,
                    "employee_count": 50,
                    "industry_sic_code": "7372",
                    "security_maturity_score": 2,
                    "has_mfa": False,
                    "has_endpoint_protection": False,
                    "has_backup_strategy": False,
                    "prior_incidents": 0,
                }
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_store = MagicMock()
        mock_store.get_guidelines.return_value = {
            "appetite": {
                "revenue_range": {"min": 500000, "max": 50000000},
                "security_requirements": {"minimum_score": 4},
                "max_prior_incidents": 3,
            }
        }

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.infrastructure.knowledge_store.get_knowledge_store",
                return_value=mock_store,
            ),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["risk_score"] >= 7
        assert "security_below_minimum" in result["flags"]
        assert result["recommendation"] == "refer"

    @pytest.mark.asyncio
    async def test_triage_guidelines_revenue_outside_appetite(self, service, submission_repo):
        """Knowledge store guidelines: revenue below minimum appetite."""
        sub = _make_submission(
            cyber_risk_data=json.dumps(
                {
                    "annual_revenue": 100000,
                    "employee_count": 5,
                    "industry_sic_code": "7372",
                    "security_maturity_score": 5,
                    "has_mfa": True,
                    "has_endpoint_protection": True,
                    "has_backup_strategy": True,
                    "prior_incidents": 0,
                }
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_store = MagicMock()
        mock_store.get_guidelines.return_value = {
            "appetite": {
                "revenue_range": {"min": 500000, "max": 50000000},
                "security_requirements": {"minimum_score": 3},
                "max_prior_incidents": 3,
            }
        }

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.infrastructure.knowledge_store.get_knowledge_store",
                return_value=mock_store,
            ),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["risk_score"] == 8
        assert "revenue_outside_appetite" in result["flags"]
        assert result["recommendation"] == "refer"

    @pytest.mark.asyncio
    async def test_triage_guidelines_incidents_exceed_max(self, service, submission_repo):
        """Knowledge store guidelines: prior incidents exceed maximum."""
        sub = _make_submission(
            cyber_risk_data=json.dumps(
                {
                    "annual_revenue": 5000000,
                    "employee_count": 50,
                    "industry_sic_code": "7372",
                    "security_maturity_score": 5,
                    "has_mfa": True,
                    "has_endpoint_protection": True,
                    "has_backup_strategy": True,
                    "prior_incidents": 5,
                }
            ),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_store = MagicMock()
        mock_store.get_guidelines.return_value = {
            "appetite": {
                "revenue_range": {"min": 500000, "max": 50000000},
                "security_requirements": {"minimum_score": 3},
                "max_prior_incidents": 3,
            }
        }

        with (
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=mock_foundry,
            ),
            patch(
                "openinsure.infrastructure.knowledge_store.get_knowledge_store",
                return_value=mock_store,
            ),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["risk_score"] == 9
        assert "incidents_exceed_maximum" in result["flags"]
        assert result["recommendation"] == "decline"


# ---------------------------------------------------------------------------
# Tests for Foundry quote with database adapter
# ---------------------------------------------------------------------------


class TestSubmissionServiceQuoteDbAdapter:
    """Foundry quote path exercising the database adapter transaction branch."""

    @pytest.mark.asyncio
    async def test_foundry_quote_with_db_transaction(self, service, submission_repo):
        """Foundry UW quote uses transaction when db adapter present."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps({"risk_score": 5, "recommendation": "proceed_to_quote"}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(
            return_value={
                "response": {
                    "recommended_premium": 20000,
                    "confidence": 0.90,
                    "reasoning": "Standard risk profile",
                },
                "source": "foundry",
                "raw": '{"recommended_premium": 20000}',
                "execution_time_ms": 150,
            }
        )

        mock_txn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_db = MagicMock()
        mock_db.transaction.return_value = mock_ctx

        # Replace repo with a mock that accepts txn kwarg
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock(return_value=sub)
        service._repo = mock_repo  # noqa: SLF001

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.agents.prompts.build_underwriting_prompt", return_value="Underwrite this"),
            patch("openinsure.agents.prompts.get_triage_context", new_callable=AsyncMock, return_value="UW guidelines"),
            patch("openinsure.agents.prompts._get_rating_breakdown", return_value=None),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=mock_db),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
        ):
            result = await service.generate_quote(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["premium"] == 20000
        mock_repo.update.assert_called()
        call_kwargs = mock_repo.update.call_args_list[0][1]
        assert "txn" in call_kwargs


# ---------------------------------------------------------------------------
# Tests for local quote fallback
# ---------------------------------------------------------------------------


class TestSubmissionServiceLocalQuoteFallback:
    """Tests for local quote generation fallback path."""

    @pytest.mark.asyncio
    async def test_local_quote_with_rating_breakdown(self, service, submission_repo):
        """Local fallback uses rating engine breakdown when available."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps({"risk_score": 5, "recommendation": "proceed_to_quote"}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch(
                "openinsure.agents.prompts._get_rating_breakdown",
                return_value={"final_premium": 12000, "base_premium": 10000},
            ),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
        ):
            result = await service.generate_quote(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["escalated"] is False
        assert result["premium"] == 12000
        assert result.get("rating_breakdown") is not None

    @pytest.mark.asyncio
    async def test_local_quote_escalation(self, service, submission_repo):
        """Local fallback quote with authority escalation."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps({"risk_score": 5, "recommendation": "proceed_to_quote"}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.agents.prompts._get_rating_breakdown", return_value=None),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": True,
                    "escalation_id": "esc-local-001",
                    "auth_result": MagicMock(
                        reason="Premium exceeds authority", required_role="senior_underwriter"
                    ),
                },
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
        ):
            result = await service.generate_quote(
                sub["id"], sub, user_role="uw_analyst", user_display_name="Junior UW"
            )

        assert result["escalated"] is True
        assert result["escalation_id"] == "esc-local-001"


# ---------------------------------------------------------------------------
# Tests for calculate_premium Foundry exception
# ---------------------------------------------------------------------------


class TestCalculatePremiumFoundryException:
    """calculate_premium when Foundry invoke throws an exception."""

    @pytest.mark.asyncio
    async def test_foundry_exception_falls_back_to_local(self, service, submission_repo):
        """When Foundry invoke fails, falls back to local rating engine."""
        sub = _make_submission(
            status="underwriting",
            triage_result=json.dumps({"risk_score": 5}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(side_effect=RuntimeError("Foundry timeout"))

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
        ):
            result = await service.calculate_premium(sub["id"], sub)

        assert result["premium"] > 0
        assert result["ai_mode"] in ("local_rating_engine", "lob_minimum_fallback")


# ---------------------------------------------------------------------------
# Tests for advanced bind paths
# ---------------------------------------------------------------------------


class TestSubmissionServiceBindAdvanced:
    """Advanced bind tests — escalation, Foundry review, db adapter, doc gen."""

    @pytest.mark.asyncio
    async def test_bind_escalation(self, service, submission_repo):
        """Bind escalation returns immediately with escalation details."""
        sub = _make_submission(status="quoted", quoted_premium=50000)
        await submission_repo.create(sub)

        with patch(
            "openinsure.services.submission_service._check_authority_and_escalate",
            new_callable=AsyncMock,
            return_value={
                "escalated": True,
                "escalation_id": "esc-bind-999",
                "auth_result": MagicMock(
                    reason="Exceeds bind authority", required_role="lob_head"
                ),
            },
        ):
            result = await service.bind(
                sub["id"], sub, user_role="uw_analyst", user_display_name="Junior UW"
            )

        assert result["escalated"] is True
        assert result["escalation_id"] == "esc-bind-999"

    @pytest.mark.asyncio
    async def test_bind_with_foundry_policy_review_and_docs(self, service, submission_repo):
        """Bind with Foundry policy review and document generation."""
        sub = _make_submission(
            status="quoted",
            quoted_premium=15000,
            triage_result=json.dumps({"risk_score": 5, "recommendation": "proceed_to_quote"}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = True
        mock_foundry.invoke = AsyncMock(
            side_effect=[
                # Policy review
                {
                    "response": {
                        "recommendation": "issue",
                        "confidence": 0.92,
                        "notes": "Policy terms are complete",
                    },
                    "source": "foundry",
                },
                # Document generation
                {
                    "response": {"title": "Declaration Page", "document_type": "declaration"},
                    "source": "foundry",
                },
            ]
        )

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.agents.prompts.build_policy_review_prompt", return_value="Review this policy"),
            patch("openinsure.agents.prompts.build_document_prompt", return_value="Generate declaration"),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch(
                "openinsure.services.submission_service.get_policy_repository",
                return_value=MagicMock(create=AsyncMock()),
            ),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
            patch("openinsure.services.bind_handlers.dispatch_bind_events", new_callable=AsyncMock),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
            patch("openinsure.api.billing.create_billing_account_on_bind", new_callable=AsyncMock),
        ):
            result = await service.bind(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["escalated"] is False
        assert "policy_id" in result
        assert result["premium"] == 15000
        assert mock_foundry.invoke.call_count == 2

    @pytest.mark.asyncio
    async def test_bind_with_db_adapter_transaction(self, service, submission_repo):
        """Bind with db adapter uses transaction for dispatch and status update."""
        sub = _make_submission(
            status="quoted",
            quoted_premium=15000,
            triage_result=json.dumps({"risk_score": 5}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_txn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_db = MagicMock()
        mock_db.transaction.return_value = mock_ctx

        # Use mock repo that accepts txn kwarg
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock(return_value=sub)
        service._repo = mock_repo  # noqa: SLF001

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=mock_db),
            patch(
                "openinsure.services.submission_service.get_policy_repository",
                return_value=MagicMock(create=AsyncMock()),
            ),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
            patch(
                "openinsure.services.bind_handlers.dispatch_bind_events",
                new_callable=AsyncMock,
            ),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
            patch("openinsure.api.billing.create_billing_account_on_bind", new_callable=AsyncMock),
        ):
            result = await service.bind(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["escalated"] is False
        assert "policy_id" in result
        mock_db.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_bind_policy_backward_compat(self, service, submission_repo):
        """bind_policy() backward compat alias delegates to bind()."""
        sub = _make_submission(
            status="quoted",
            quoted_premium=15000,
            triage_result=json.dumps({"risk_score": 5}),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch(
                "openinsure.services.submission_service.get_policy_repository",
                return_value=MagicMock(create=AsyncMock()),
            ),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
            patch(
                "openinsure.services.bind_handlers.dispatch_bind_events",
                new_callable=AsyncMock,
            ),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
            patch("openinsure.api.billing.create_billing_account_on_bind", new_callable=AsyncMock),
        ):
            result = await service.bind_policy(sub["id"], sub, user_role="underwriter")

        assert result["escalated"] is False
        assert "policy_id" in result


# ---------------------------------------------------------------------------
# Tests for process() method
# ---------------------------------------------------------------------------


class TestSubmissionServiceProcess:
    """Tests for the full process() workflow method."""

    @pytest.mark.asyncio
    async def test_process_full_workflow_success(self, service, submission_repo):
        """Full workflow: triage → quote → authority → bind."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-123"
        mock_execution.steps_completed = [
            {"name": "intake", "response": {"risk_score": 5, "appetite_match": "yes"}},
            {"name": "underwriting", "response": {"recommended_premium": 15000, "confidence": 0.88}},
        ]

        mock_policy_repo = MagicMock()
        mock_policy_repo.create = AsyncMock()
        mock_billing_repo = MagicMock()
        mock_billing_repo.create = AsyncMock()

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
            patch("openinsure.services.submission_service.get_policy_repository", return_value=mock_policy_repo),
            patch("openinsure.services.submission_service.get_billing_repository", return_value=mock_billing_repo),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.process(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["outcome"] == "bound"
        assert result["premium"] == 15000
        assert result["policy_id"] is not None
        assert result["policy_number"] is not None
        assert result["workflow_id"] == "wf-123"
        mock_policy_repo.create.assert_called_once()
        mock_billing_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_decline_outside_appetite(self, service, submission_repo):
        """Workflow declines when triage says outside appetite."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-456"
        mock_execution.steps_completed = [
            {"name": "intake", "response": {"risk_score": 9, "appetite_match": "decline"}},
            {"name": "underwriting", "response": {"recommended_premium": 0}},
        ]

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
        ):
            result = await service.process(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["outcome"] == "declined"
        assert result["reason"] == "outside_appetite"
        assert result["policy_id"] is None
        assert result["premium"] is None

    @pytest.mark.asyncio
    async def test_process_escalation(self, service, submission_repo):
        """Workflow escalates when authority insufficient."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-789"
        mock_execution.steps_completed = [
            {"name": "intake", "response": {"risk_score": 5, "appetite_match": "yes"}},
            {"name": "underwriting", "response": {"recommended_premium": 15000}},
        ]

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": True,
                    "escalation_id": "esc-process-001",
                    "auth_result": MagicMock(decision="escalate", reason="Premium exceeds authority"),
                },
            ),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.process(
                sub["id"], sub, user_role="uw_analyst", user_display_name="Junior UW"
            )

        assert result["outcome"] == "quoted_pending_approval"
        assert result["escalation_id"] == "esc-process-001"
        assert result["policy_id"] is None

    @pytest.mark.asyncio
    async def test_process_string_triage_response_decline(self, service, submission_repo):
        """Process handles string triage response containing decline keywords."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-str-dec"
        mock_execution.steps_completed = [
            {"name": "intake", "response": "This submission is outside appetite - decline"},
            {"name": "underwriting", "response": {}},
        ]

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
        ):
            result = await service.process(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["outcome"] == "declined"

    @pytest.mark.asyncio
    async def test_process_string_triage_response_accept(self, service, submission_repo):
        """Process handles string triage response without decline keywords."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-str-acc"
        mock_execution.steps_completed = [
            {"name": "intake", "response": "This submission is within appetite, proceed"},
            {"name": "underwriting", "response": {"recommended_premium": 10000}},
        ]

        mock_policy_repo = MagicMock()
        mock_policy_repo.create = AsyncMock()
        mock_billing_repo = MagicMock()
        mock_billing_repo.create = AsyncMock()

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.services.submission_service._check_authority_and_escalate",
                new_callable=AsyncMock,
                return_value={
                    "escalated": False,
                    "auth_result": MagicMock(decision="auto_execute", reason="Within limit"),
                },
            ),
            patch("openinsure.services.submission_service.get_policy_repository", return_value=mock_policy_repo),
            patch("openinsure.services.submission_service.get_billing_repository", return_value=mock_billing_repo),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.process(
                sub["id"], sub, user_role="underwriter", user_display_name="Test UW"
            )

        assert result["outcome"] == "bound"
        assert result["premium"] == 10000


class TestCheckAuthorityAndEscalate:
    """Tests for the _check_authority_and_escalate helper."""

    @pytest.mark.asyncio
    async def test_quote_auto_execute(self):
        """Small premium auto-executes for quote."""
        from openinsure.services.submission_service import _check_authority_and_escalate

        result = await _check_authority_and_escalate(
            action="quote",
            premium=5000,
            user_role="openinsure-senior-underwriter",
            user_display_name="Test UW",
            entity_id="sub-1",
        )
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_bind_auto_execute(self):
        """Small premium auto-executes for bind."""
        from openinsure.services.submission_service import _check_authority_and_escalate

        result = await _check_authority_and_escalate(
            action="bind",
            premium=5000,
            user_role="openinsure-senior-underwriter",
            user_display_name="Test UW",
            entity_id="sub-1",
        )
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_escalation_with_work_item(self):
        """Large premium from analyst triggers escalation."""
        from openinsure.services.escalation import _escalation_queue
        from openinsure.services.submission_service import _check_authority_and_escalate

        _escalation_queue.clear()
        result = await _check_authority_and_escalate(
            action="quote",
            premium=75000,
            user_role="openinsure-uw-analyst",
            user_display_name="Junior UW",
            entity_id="sub-esc",
        )
        assert result["escalated"] is True
        assert "escalation_id" in result
        _escalation_queue.clear()


class TestSubmissionServiceTriageLocalFallback:
    """Tests for local triage fallback with knowledge guidelines."""

    @pytest.mark.asyncio
    async def test_triage_guidelines_revenue_outside_appetite(self, service, submission_repo):
        """Revenue outside appetite range triggers referral."""
        sub = _make_submission(
            cyber_risk_data=json.dumps({
                "annual_revenue": 100,
                "employee_count": 5,
                "industry_sic_code": "7372",
                "security_maturity_score": 8.0,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "prior_incidents": 0,
            }),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_knowledge = MagicMock()
        mock_knowledge.get_guidelines = MagicMock(return_value={
            "appetite": {
                "revenue_range": {"min": 500000, "max": 50000000},
                "security_requirements": {"minimum_score": 4},
                "max_prior_incidents": 3,
            }
        })

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.infrastructure.knowledge_store.get_knowledge_store", return_value=mock_knowledge),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["status"] == "underwriting"
        assert "revenue_outside_appetite" in result["flags"]
        assert result["recommendation"] == "refer"

    @pytest.mark.asyncio
    async def test_triage_guidelines_security_below_minimum(self, service, submission_repo):
        """Security score below minimum triggers referral."""
        sub = _make_submission(
            cyber_risk_data=json.dumps({
                "annual_revenue": 5000000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 2.0,
                "has_mfa": False,
                "has_endpoint_protection": False,
                "has_backup_strategy": False,
                "prior_incidents": 0,
            }),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_knowledge = MagicMock()
        mock_knowledge.get_guidelines = MagicMock(return_value={
            "appetite": {
                "revenue_range": {"min": 500000, "max": 50000000},
                "security_requirements": {"minimum_score": 4},
                "max_prior_incidents": 3,
            }
        })

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.infrastructure.knowledge_store.get_knowledge_store", return_value=mock_knowledge),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["status"] == "underwriting"
        assert "security_below_minimum" in result["flags"]

    @pytest.mark.asyncio
    async def test_triage_guidelines_incidents_exceed(self, service, submission_repo):
        """Prior incidents exceeding max triggers decline."""
        sub = _make_submission(
            cyber_risk_data=json.dumps({
                "annual_revenue": 5000000,
                "employee_count": 50,
                "industry_sic_code": "7372",
                "security_maturity_score": 5.0,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "prior_incidents": 10,
            }),
        )
        await submission_repo.create(sub)

        mock_foundry = MagicMock()
        mock_foundry.is_available = False

        mock_knowledge = MagicMock()
        mock_knowledge.get_guidelines = MagicMock(return_value={
            "appetite": {
                "revenue_range": {"min": 500000, "max": 50000000},
                "security_requirements": {"minimum_score": 4},
                "max_prior_incidents": 3,
            }
        })

        with (
            patch("openinsure.agents.foundry_client.get_foundry_client", return_value=mock_foundry),
            patch("openinsure.infrastructure.knowledge_store.get_knowledge_store", return_value=mock_knowledge),
        ):
            result = await service.run_triage(sub["id"], sub)

        assert result["status"] == "underwriting"
        assert "incidents_exceed_maximum" in result["flags"]
        assert result["recommendation"] == "decline"


class TestSubmissionServiceProcess:
    """Tests for the full process workflow."""

    @pytest.mark.asyncio
    async def test_process_full_workflow_success(self, service, submission_repo):
        """Full workflow: triage→quote→authority→bind."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-123"
        mock_execution.steps_completed = [
            {"name": "intake", "response": {"risk_score": 5, "appetite_match": "yes"}},
            {"name": "underwriting", "response": {"recommended_premium": 12000, "confidence": 0.88}},
        ]

        mock_policy_repo = MagicMock()
        mock_policy_repo.create = AsyncMock()
        mock_billing_repo = MagicMock()
        mock_billing_repo.create = AsyncMock()

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch("openinsure.services.submission_service.get_policy_repository", return_value=mock_policy_repo),
            patch("openinsure.services.submission_service.get_billing_repository", return_value=mock_billing_repo),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
        ):
            result = await service.process(
                sub["id"],
                sub,
                user_role="openinsure-senior-underwriter",
                user_display_name="Test UW",
            )

        assert result["workflow"] == "new_business"
        assert result["outcome"] in ("bound", "quoted_pending_approval")
        assert result["premium"] == 12000

    @pytest.mark.asyncio
    async def test_process_decline_outside_appetite(self, service, submission_repo):
        """Workflow declines when triage says outside appetite."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-decline"
        mock_execution.steps_completed = [
            {"name": "intake", "response": {"appetite_match": "decline"}},
            {"name": "underwriting", "response": {"recommended_premium": 0}},
        ]

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.process(
                sub["id"],
                sub,
                user_role="openinsure-senior-underwriter",
                user_display_name="Test UW",
            )

        assert result["outcome"] == "declined"
        assert result["reason"] == "outside_appetite"
        assert result["policy_id"] is None

    @pytest.mark.asyncio
    async def test_process_escalation(self, service, submission_repo):
        """Workflow escalates when authority is insufficient."""
        from openinsure.services.escalation import _escalation_queue

        _escalation_queue.clear()

        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-esc"
        mock_execution.steps_completed = [
            {"name": "intake", "response": {"risk_score": 5, "appetite_match": "yes"}},
            {"name": "underwriting", "response": {"recommended_premium": 150000, "confidence": 0.85}},
        ]

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
        ):
            result = await service.process(
                sub["id"],
                sub,
                user_role="openinsure-uw-analyst",
                user_display_name="Junior UW",
            )

        assert result["outcome"] == "quoted_pending_approval"
        assert result["policy_id"] is None
        assert result["escalation_id"] is not None
        _escalation_queue.clear()

    @pytest.mark.asyncio
    async def test_process_string_triage_response(self, service, submission_repo):
        """Handles string triage responses (non-dict)."""
        sub = _make_submission()
        await submission_repo.create(sub)

        mock_execution = MagicMock()
        mock_execution.id = "wf-str"
        mock_execution.steps_completed = [
            {"name": "intake", "response": "This is within appetite, proceed to underwriting."},
            {"name": "underwriting", "response": {"recommended_premium": 8000}},
        ]

        mock_policy_repo = MagicMock()
        mock_policy_repo.create = AsyncMock()
        mock_billing_repo = MagicMock()
        mock_billing_repo.create = AsyncMock()

        with (
            patch(
                "openinsure.services.workflow_engine.execute_workflow",
                new_callable=AsyncMock,
                return_value=mock_execution,
            ),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch(
                "openinsure.infrastructure.factory.get_compliance_repository",
                return_value=MagicMock(store_decision=AsyncMock()),
            ),
            patch("openinsure.services.submission_service.get_policy_repository", return_value=mock_policy_repo),
            patch("openinsure.services.submission_service.get_billing_repository", return_value=mock_billing_repo),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
        ):
            result = await service.process(
                sub["id"],
                sub,
                user_role="openinsure-senior-underwriter",
                user_display_name="Test UW",
            )

        assert result["workflow"] == "new_business"
        assert result["premium"] == 8000


class TestBindPolicyBackwardCompat:
    """Tests for backward-compatible bind_policy alias."""

    @pytest.mark.asyncio
    async def test_bind_policy_alias(self, service, submission_repo):
        """bind_policy() delegates to bind() with system user."""
        sub = _make_submission(
            status="quoted",
            quoted_premium=8000,
            triage_result=json.dumps({"risk_score": 5}),
        )
        await submission_repo.create(sub)

        mock_policy_repo = MagicMock()
        mock_policy_repo.create = AsyncMock()

        with (
            patch("openinsure.services.submission_service.get_policy_repository", return_value=mock_policy_repo),
            patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None),
            patch("openinsure.services.submission_service._auto_cession", new_callable=AsyncMock),
            patch("openinsure.services.event_publisher.publish_domain_event", new_callable=AsyncMock),
            patch("openinsure.api.billing.create_billing_account_on_bind", new_callable=AsyncMock),
            patch(
                "openinsure.agents.foundry_client.get_foundry_client",
                return_value=MagicMock(is_available=False),
            ),
        ):
            result = await service.bind_policy(sub["id"], sub, user_role="openinsure-senior-underwriter")

        assert result.get("escalated") is False or "policy_id" in result


class TestBuildPolicyData:
    """Tests for _build_policy_data helper."""

    def test_build_policy_data_all_coverages(self):
        """Verify all 5 coverages are created with correct codes."""
        from openinsure.services.submission_service import _build_policy_data

        sub = _make_submission(quoted_premium=10000)
        data = _build_policy_data(sub, 10000.0, policy_id="p1", policy_number="POL-1")

        assert data["id"] == "p1"
        assert data["policy_number"] == "POL-1"
        assert data["status"] == "active"
        assert len(data["coverages"]) == 5
        coverage_codes = [c["coverage_code"] for c in data["coverages"]]
        assert "BREACH-RESP" in coverage_codes
        assert "THIRD-PARTY" in coverage_codes
        assert "REG-DEFENSE" in coverage_codes
        assert "BUS-INTERRUPT" in coverage_codes
        assert "RANSOMWARE" in coverage_codes
        assert data["total_premium"] == 10000.0
        assert data["written_premium"] == 10000.0
