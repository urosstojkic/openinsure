"""Tests for openinsure.services.claims_processing.ClaimsProcessingService."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from openinsure.domain.claim import CauseOfLoss, Claim, ClaimStatus, SeverityTier
from openinsure.domain.policy import Policy, PolicyStatus
from openinsure.services.claims_processing import (
    ClaimsProcessingService,
    FNOLRequest,
    PaymentRequest,
    ReserveRequest,
)


@pytest.fixture()
def svc():
    return ClaimsProcessingService()


@pytest.fixture()
def fnol_request():
    return FNOLRequest(
        policy_id=uuid4(),
        loss_date=date(2025, 6, 1),
        report_date=date(2025, 6, 2),
        loss_type="cyber",
        cause_of_loss=CauseOfLoss.data_breach,
        description="Sensitive data exposed in breach",
        severity=SeverityTier.moderate,
    )


def _make_claim(**overrides) -> Claim:
    defaults = dict(
        claim_number="CLM-TEST0001",
        status=ClaimStatus.fnol,
        policy_id=uuid4(),
        loss_date=date(2025, 6, 1),
        report_date=date(2025, 6, 2),
        loss_type="cyber",
        cause_of_loss=CauseOfLoss.data_breach,
        description="Test claim",
        severity=SeverityTier.moderate,
    )
    defaults.update(overrides)
    return Claim(**defaults)


def _make_policy(*, status=PolicyStatus.active, effective=date(2025, 1, 1), expiration=date(2026, 1, 1)) -> Policy:
    return Policy(
        policy_number="POL-0001",
        status=status,
        product_id=uuid4(),
        submission_id=uuid4(),
        insured_id=uuid4(),
        effective_date=effective,
        expiration_date=expiration,
        total_premium=Decimal("10000"),
        written_premium=Decimal("10000"),
        earned_premium=Decimal("5000"),
        unearned_premium=Decimal("5000"),
    )


# ---------- FNOL intake ----------


class TestFNOLIntake:
    def test_intake_fnol_creates_claim(self, svc, fnol_request):
        result = svc.intake_fnol(fnol_request)

        assert result.claim.claim_number.startswith("CLM-")
        assert result.claim.status == ClaimStatus.fnol
        assert result.claim.policy_id == fnol_request.policy_id
        assert result.claim.cause_of_loss == CauseOfLoss.data_breach
        assert result.claim.severity == SeverityTier.moderate
        assert "created" in result.message.lower()

    def test_intake_fnol_emits_event(self, svc, fnol_request):
        result = svc.intake_fnol(fnol_request)

        assert len(result.events) == 1
        event = result.events[0]
        assert event.event_type == "claim.reported"
        assert event.aggregate_id == result.claim.id
        assert event.payload["cause_of_loss"] == "data_breach"


# ---------- Coverage verification ----------


class TestCoverageVerification:
    def test_verify_coverage_active_in_period(self, svc):
        claim = _make_claim(loss_date=date(2025, 6, 1))
        policy = _make_policy(status=PolicyStatus.active, effective=date(2025, 1, 1), expiration=date(2026, 1, 1))

        result = svc.verify_coverage(claim, policy)

        assert result.is_covered is True
        assert result.policy_active is True
        assert result.loss_within_period is True
        assert result.exclusions_apply is False

    def test_verify_coverage_inactive_policy(self, svc):
        claim = _make_claim(loss_date=date(2025, 6, 1))
        policy = _make_policy(status=PolicyStatus.expired)

        result = svc.verify_coverage(claim, policy)

        assert result.is_covered is False
        assert result.policy_active is False
        assert any("expired" in r.lower() or "status" in r.lower() for r in result.reasons)

    def test_verify_coverage_loss_outside_period(self, svc):
        claim = _make_claim(loss_date=date(2027, 6, 1))
        policy = _make_policy(effective=date(2025, 1, 1), expiration=date(2026, 1, 1))

        result = svc.verify_coverage(claim, policy)

        assert result.is_covered is False
        assert result.loss_within_period is False

    def test_verify_coverage_other_cause_exclusion(self, svc):
        claim = _make_claim(cause_of_loss=CauseOfLoss.other)
        policy = _make_policy()

        result = svc.verify_coverage(claim, policy)

        assert result.is_covered is False
        assert result.exclusions_apply is True
        assert any("other" in r.lower() for r in result.reasons)


# ---------- Reserves ----------


class TestReserves:
    def test_set_reserves_explicit_amount(self, svc):
        claim = _make_claim()
        req = ReserveRequest(amount=Decimal("50000"), set_by="adjuster", confidence=0.9)

        result = svc.set_reserves(claim, req)

        assert result.claim.status == ClaimStatus.reserved
        assert len(result.claim.reserves) == 1
        assert result.claim.reserves[0].amount == Decimal("50000")
        assert result.events[0].event_type == "claim.reserved"

    def test_set_reserves_auto_from_severity(self, svc):
        claim = _make_claim(severity=SeverityTier.simple)

        result = svc.set_reserves(claim, request=None)

        assert result.claim.status == ClaimStatus.reserved
        assert len(result.claim.reserves) == 1
        assert result.claim.reserves[0].amount > 0
        assert result.claim.reserves[0].set_by == "system"


# ---------- Payments ----------


class TestPayments:
    def test_process_payment_success(self, svc):
        claim = _make_claim(status=ClaimStatus.reserved)
        req = PaymentRequest(amount=Decimal("10000"), payee_id=uuid4())

        result = svc.process_payment(claim, req)

        assert result.claim.status == ClaimStatus.settling
        assert len(result.claim.payments) == 1
        assert result.claim.payments[0].amount == Decimal("10000")
        assert result.events[0].event_type == "claim.paid"

    def test_process_payment_closed_claim_raises(self, svc):
        claim = _make_claim(status=ClaimStatus.closed)
        req = PaymentRequest(amount=Decimal("5000"), payee_id=uuid4())

        with pytest.raises(ValueError, match="Cannot process payment"):
            svc.process_payment(claim, req)


# ---------- Close claim ----------


class TestCloseClaim:
    def test_close_claim_success(self, svc):
        claim = _make_claim(status=ClaimStatus.settling)

        result = svc.close_claim(claim, "Settlement reached")

        assert result.claim.status == ClaimStatus.closed
        assert result.claim.close_reason == "Settlement reached"
        assert result.claim.closed_at is not None
        assert result.events[0].event_type == "claim.closed"

    def test_close_already_closed_raises(self, svc):
        claim = _make_claim(status=ClaimStatus.closed)

        with pytest.raises(ValueError, match="already closed"):
            svc.close_claim(claim, "Duplicate close")
