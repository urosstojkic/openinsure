"""Tests for PolicyLifecycleService and pure helper functions.

Covers binding, endorsement, renewal, cancellation, reinstatement,
and all pure premium/validation helpers in policy_lifecycle.py.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from openinsure.domain.common import new_id
from openinsure.domain.policy import Coverage, Policy, PolicyStatus
from openinsure.domain.state_machine import InvalidTransitionError
from openinsure.domain.submission import Submission, SubmissionChannel
from openinsure.services.policy_lifecycle import (
    BindRequest,
    CancellationRequest,
    EndorsementRequest,
    PolicyLifecycleService,
    calculate_earned_unearned,
    calculate_endorsement_premium,
    compute_renewal_factor,
    earned_premium_fraction,
    validate_bind_requirements,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATCH_RECORD = "openinsure.services.policy_lifecycle.record_transaction"


def _make_submission(**overrides) -> Submission:
    defaults = dict(
        submission_number="SUB-001",
        channel=SubmissionChannel.api,
        line_of_business="cyber",
        applicant=uuid4(),
        requested_effective_date=date(2025, 1, 1),
        requested_expiration_date=date(2026, 1, 1),
    )
    defaults.update(overrides)
    return Submission(**defaults)


def _make_coverage(**overrides) -> Coverage:
    defaults = dict(
        coverage_code="CYB-001",
        coverage_name="Cyber Liability",
        limit=Decimal("1000000.00"),
        deductible=Decimal("10000.00"),
        premium=Decimal("5000.00"),
    )
    defaults.update(overrides)
    return Coverage(**defaults)


def _make_policy(**overrides) -> Policy:
    defaults = dict(
        policy_number="POL-TEST0001",
        status=PolicyStatus.active,
        product_id=new_id(),
        submission_id=new_id(),
        insured_id=new_id(),
        effective_date=date(2025, 1, 1),
        expiration_date=date(2026, 1, 1),
        coverages=[_make_coverage()],
        total_premium=Decimal("10000.00"),
        written_premium=Decimal("10000.00"),
        earned_premium=Decimal("0.00"),
        unearned_premium=Decimal("10000.00"),
    )
    defaults.update(overrides)
    return Policy(**defaults)


# ===================================================================
# Pure helpers
# ===================================================================


class TestPureHelpers:
    """Tests for the pure business-logic helper functions."""

    # --- validate_bind_requirements ---

    def test_validate_bind_requirements_valid(self):
        quote = {"terms": {"limit": 1_000_000}, "authority": {}}
        submission = {"line_of_business": "cyber"}
        errors = validate_bind_requirements(quote, submission)
        assert errors == []

    def test_validate_bind_requirements_no_terms(self):
        quote = {"authority": {}}
        submission = {"line_of_business": "cyber"}
        errors = validate_bind_requirements(quote, submission)
        assert "Quote has no terms" in errors

    def test_validate_bind_requirements_referral_needed(self):
        quote = {
            "terms": {"limit": 1_000_000},
            "authority": {"requires_referral": True, "referral_approved": False},
        }
        submission = {"line_of_business": "cyber"}
        errors = validate_bind_requirements(quote, submission)
        assert "Quote requires referral approval before binding" in errors

    # --- calculate_endorsement_premium ---

    def test_endorsement_premium_explicit(self):
        result = calculate_endorsement_premium(
            {"premium_change": "250.00"},
            Decimal("10000.00"),
        )
        assert result == Decimal("250.00")

    def test_endorsement_premium_increase_limit(self):
        result = calculate_endorsement_premium(
            {"change_type": "increase_limit"},
            Decimal("10000.00"),
        )
        assert result == Decimal("1500.00")

    def test_endorsement_premium_decrease_limit(self):
        result = calculate_endorsement_premium(
            {"change_type": "decrease_limit"},
            Decimal("10000.00"),
        )
        assert result == Decimal("-1000.00")

    def test_endorsement_premium_unknown_type(self):
        result = calculate_endorsement_premium(
            {"change_type": "unknown_type"},
            Decimal("10000.00"),
        )
        assert result == Decimal("0.00")

    # --- compute_renewal_factor ---

    def test_renewal_factor_no_claims(self):
        assert compute_renewal_factor([]) == Decimal("0.95")

    def test_renewal_factor_one_small_claim(self):
        claims = [{"total_incurred": "5000"}]
        assert compute_renewal_factor(claims) == Decimal("1.05")

    def test_renewal_factor_many_claims(self):
        claims = [
            {"total_incurred": "50000"},
            {"total_incurred": "60000"},
            {"total_incurred": "70000"},
        ]
        assert compute_renewal_factor(claims) == Decimal("1.35")

    # --- earned_premium_fraction ---

    def test_earned_premium_fraction_mid_term(self):
        eff = date(2025, 1, 1)
        exp = date(2026, 1, 1)
        mid = date(2025, 7, 1)
        frac = earned_premium_fraction(eff, exp, mid)
        # 181 out of 365 days
        expected = (Decimal("181") / Decimal("365")).quantize(Decimal("0.0001"))
        assert frac == expected

    def test_earned_premium_fraction_at_start(self):
        eff = date(2025, 1, 1)
        exp = date(2026, 1, 1)
        frac = earned_premium_fraction(eff, exp, eff)
        assert frac == Decimal("0.0000")

    def test_earned_premium_fraction_at_end(self):
        eff = date(2025, 1, 1)
        exp = date(2026, 1, 1)
        frac = earned_premium_fraction(eff, exp, exp)
        assert frac == Decimal("1.0000")

    # --- calculate_earned_unearned ---

    def test_calculate_earned_unearned_mid_term(self):
        earned, unearned = calculate_earned_unearned(
            total_premium=Decimal("12000.00"),
            effective_date="2025-01-01",
            expiration_date="2026-01-01",
            cancel_date="2025-07-01",
        )
        # 181 / 365 * 12000 = 5950.68 (rounded)
        assert earned + unearned == Decimal("12000.00")
        assert earned > Decimal("0")
        assert unearned > Decimal("0")


# ===================================================================
# Service tests
# ===================================================================


class TestPolicyLifecycleService:
    """Tests for the PolicyLifecycleService async methods."""

    @pytest.mark.asyncio
    @patch(_PATCH_RECORD, new_callable=AsyncMock)
    async def test_bind_policy(self, mock_record):
        svc = PolicyLifecycleService()
        sub = _make_submission()
        cov = [_make_coverage()]
        req = BindRequest(
            submission=sub,
            coverages=cov,
            effective_date=date(2025, 1, 1),
            expiration_date=date(2026, 1, 1),
            total_premium=Decimal("10000.00"),
        )

        result = await svc.bind_policy(req)

        assert result.policy.status == PolicyStatus.active
        assert result.policy.policy_number.startswith("POL-")
        assert result.policy.total_premium == Decimal("10000.00")
        assert result.policy.bound_at is not None
        assert len(result.events) == 1
        assert result.events[0].event_type == "policy.bound"
        assert "bound successfully" in result.message
        mock_record.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_PATCH_RECORD, new_callable=AsyncMock)
    async def test_endorse_policy(self, mock_record):
        svc = PolicyLifecycleService()
        policy = _make_policy()
        req = EndorsementRequest(
            description="Increase cyber limit",
            effective_date=date(2025, 6, 1),
            premium_change=Decimal("500.00"),
            coverages_modified=["CYB-001"],
        )

        result = await svc.endorse_policy(policy, req)

        assert result.policy.total_premium == Decimal("10500.00")
        assert len(result.policy.endorsements) == 1
        assert result.events[0].event_type == "policy.endorsed"
        assert "END-001" in result.policy.endorsements[0].endorsement_number
        mock_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_endorse_inactive_policy_raises(self):
        svc = PolicyLifecycleService()
        policy = _make_policy(status=PolicyStatus.cancelled)
        req = EndorsementRequest(
            description="Attempt endorsement",
            effective_date=date(2025, 6, 1),
            premium_change=Decimal("100.00"),
        )

        with pytest.raises(ValueError, match="Cannot endorse policy"):
            await svc.endorse_policy(policy, req)

    @pytest.mark.asyncio
    @patch(_PATCH_RECORD, new_callable=AsyncMock)
    async def test_cancel_policy(self, mock_record):
        svc = PolicyLifecycleService()
        policy = _make_policy(status=PolicyStatus.active)
        req = CancellationRequest(
            reason="Insured request",
            effective_date=date(2025, 7, 1),
        )

        result = await svc.cancel_policy(policy, req)

        assert result.policy.status == PolicyStatus.cancelled
        assert result.policy.cancel_reason == "Insured request"
        assert result.policy.cancelled_at is not None
        assert result.policy.earned_premium > Decimal("0")
        assert result.policy.earned_premium + result.policy.unearned_premium == Decimal("10000.00")
        assert result.events[0].event_type == "policy.cancelled"
        mock_record.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(_PATCH_RECORD, new_callable=AsyncMock)
    async def test_renew_policy(self, mock_record):
        svc = PolicyLifecycleService()
        policy = _make_policy(status=PolicyStatus.active)

        result = await svc.renew_policy(policy)

        renewal = result.policy
        assert renewal.policy_number.startswith("POL-")
        assert renewal.policy_number != policy.policy_number
        assert renewal.status == PolicyStatus.active
        assert renewal.effective_date == policy.expiration_date
        assert renewal.total_premium == policy.total_premium
        assert renewal.earned_premium == Decimal("0.00")
        assert result.events[0].event_type == "policy.renewed"
        mock_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_renew_cancelled_raises(self):
        svc = PolicyLifecycleService()
        policy = _make_policy(status=PolicyStatus.cancelled)

        with pytest.raises(ValueError, match="Cannot renew policy"):
            await svc.renew_policy(policy)

    @pytest.mark.asyncio
    @patch(_PATCH_RECORD, new_callable=AsyncMock)
    async def test_reinstate_policy(self, mock_record):
        svc = PolicyLifecycleService()
        policy = _make_policy(status=PolicyStatus.cancelled)

        result = await svc.reinstate_policy(policy)

        assert result.policy.status == PolicyStatus.reinstated
        assert "reinstated" in result.message
        mock_record.assert_awaited_once()
