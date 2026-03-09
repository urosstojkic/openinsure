"""Tests for the Claim domain entity."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from openinsure.domain.claim import (
    CauseOfLoss,
    Claim,
    ClaimDocument,
    ClaimStatus,
    Payment,
    Reserve,
    SeverityTier,
)


def _make_claim(**overrides) -> Claim:
    """Helper to create a claim with sensible defaults."""
    defaults = {
        "claim_number": "CLM-TEST-001",
        "status": ClaimStatus.fnol,
        "policy_id": uuid4(),
        "loss_date": date(2026, 9, 15),
        "report_date": date(2026, 9, 16),
        "loss_type": "cyber_incident",
        "cause_of_loss": CauseOfLoss.ransomware,
        "description": "Ransomware attack encrypted critical systems",
        "severity": SeverityTier.complex,
    }
    defaults.update(overrides)
    return Claim(**defaults)


def _make_reserve(**overrides) -> Reserve:
    """Helper to create a reserve."""
    defaults = {
        "reserve_type": "indemnity",
        "amount": Decimal("50000.00"),
        "set_date": datetime.now(UTC),
        "set_by": "system",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return Reserve(**defaults)


def _make_payment(**overrides) -> Payment:
    """Helper to create a payment."""
    defaults = {
        "amount": Decimal("25000.00"),
        "payee_id": uuid4(),
        "payment_date": datetime.now(UTC),
        "payment_type": "indemnity",
    }
    defaults.update(overrides)
    return Payment(**defaults)


class TestCreateClaim:
    """Test creating a claim."""

    def test_create_claim(self):
        claim = _make_claim()
        assert claim.claim_number == "CLM-TEST-001"
        assert claim.status == ClaimStatus.fnol
        assert claim.cause_of_loss == CauseOfLoss.ransomware
        assert claim.severity == SeverityTier.complex
        assert claim.id is not None

    def test_claim_defaults(self):
        claim = _make_claim()
        assert claim.reserves == []
        assert claim.payments == []
        assert claim.documents == []
        assert claim.assigned_adjuster is None
        assert claim.closed_at is None

    def test_claim_with_claimants(self):
        claimant_ids = [uuid4(), uuid4()]
        claim = _make_claim(claimant_ids=claimant_ids)
        assert len(claim.claimant_ids) == 2


class TestClaimWithReserves:
    """Test claim with reserves."""

    def test_claim_with_reserves(self):
        reserve = _make_reserve()
        claim = _make_claim(reserves=[reserve])
        assert len(claim.reserves) == 1
        assert claim.reserves[0].amount == Decimal("50000.00")

    def test_claim_with_multiple_reserves(self):
        reserves = [
            _make_reserve(reserve_type="indemnity", amount=Decimal("50000.00")),
            _make_reserve(reserve_type="expense", amount=Decimal("15000.00")),
        ]
        claim = _make_claim(reserves=reserves)
        assert len(claim.reserves) == 2

    def test_reserve_confidence_validation(self):
        reserve = _make_reserve(confidence=0.95)
        assert reserve.confidence == 0.95


class TestClaimPayments:
    """Test claim payments."""

    def test_claim_payments(self):
        payment = _make_payment()
        claim = _make_claim(payments=[payment])
        assert len(claim.payments) == 1
        assert claim.payments[0].amount == Decimal("25000.00")

    def test_claim_with_multiple_payments(self):
        payments = [
            _make_payment(amount=Decimal("10000.00"), payment_type="indemnity"),
            _make_payment(amount=Decimal("5000.00"), payment_type="expense"),
        ]
        claim = _make_claim(payments=payments)
        assert len(claim.payments) == 2

    def test_payment_has_unique_id(self):
        p1 = _make_payment()
        p2 = _make_payment()
        assert p1.payment_id != p2.payment_id


class TestTotalIncurredComputation:
    """Test total_incurred computed field."""

    def test_total_incurred_computation(self):
        reserves = [
            _make_reserve(amount=Decimal("50000.00")),
            _make_reserve(amount=Decimal("20000.00")),
        ]
        payments = [
            _make_payment(amount=Decimal("10000.00")),
        ]
        claim = _make_claim(reserves=reserves, payments=payments)
        assert claim.total_incurred == Decimal("80000.00")

    def test_total_incurred_no_financials(self):
        claim = _make_claim()
        assert claim.total_incurred == Decimal("0.00")

    def test_total_incurred_reserves_only(self):
        reserves = [_make_reserve(amount=Decimal("30000.00"))]
        claim = _make_claim(reserves=reserves)
        assert claim.total_incurred == Decimal("30000.00")

    def test_total_incurred_payments_only(self):
        payments = [_make_payment(amount=Decimal("15000.00"))]
        claim = _make_claim(payments=payments)
        assert claim.total_incurred == Decimal("15000.00")


class TestClaimStatusTransitions:
    """Test claim status transitions."""

    def test_transition_to_investigating(self):
        claim = _make_claim()
        claim.status = ClaimStatus.investigating
        assert claim.status == ClaimStatus.investigating

    def test_transition_to_reserved(self):
        claim = _make_claim()
        claim.status = ClaimStatus.reserved
        assert claim.status == ClaimStatus.reserved

    def test_transition_to_settling(self):
        claim = _make_claim()
        claim.status = ClaimStatus.settling
        assert claim.status == ClaimStatus.settling

    def test_transition_to_closed(self):
        claim = _make_claim()
        claim.status = ClaimStatus.closed
        claim.closed_at = datetime.now(UTC)
        claim.close_reason = "Settled"
        assert claim.status == ClaimStatus.closed

    def test_transition_to_denied(self):
        claim = _make_claim()
        claim.status = ClaimStatus.denied
        assert claim.status == ClaimStatus.denied

    def test_transition_to_reopened(self):
        claim = _make_claim()
        claim.status = ClaimStatus.closed
        claim.status = ClaimStatus.reopened
        assert claim.status == ClaimStatus.reopened


class TestSeverityAssessment:
    """Test severity tier assessment."""

    def test_simple_severity(self):
        claim = _make_claim(severity=SeverityTier.simple)
        assert claim.severity == SeverityTier.simple

    def test_moderate_severity(self):
        claim = _make_claim(severity=SeverityTier.moderate)
        assert claim.severity == SeverityTier.moderate

    def test_complex_severity(self):
        claim = _make_claim(severity=SeverityTier.complex)
        assert claim.severity == SeverityTier.complex

    def test_catastrophe_severity(self):
        claim = _make_claim(severity=SeverityTier.catastrophe)
        assert claim.severity == SeverityTier.catastrophe

    def test_all_cause_of_loss_values(self):
        for cause in CauseOfLoss:
            claim = _make_claim(cause_of_loss=cause)
            assert claim.cause_of_loss == cause


class TestClaimSerialization:
    """Test claim serialization."""

    def test_claim_serialization(self):
        claim = _make_claim()
        data = claim.model_dump()
        assert data["claim_number"] == "CLM-TEST-001"
        assert data["status"] == "fnol"
        assert data["cause_of_loss"] == "ransomware"
        assert data["severity"] == "complex"

    def test_claim_roundtrip(self):
        reserve = _make_reserve()
        payment = _make_payment()
        claim = _make_claim(reserves=[reserve], payments=[payment])
        data = claim.model_dump()
        restored = Claim(**data)
        assert restored.claim_number == claim.claim_number
        assert restored.id == claim.id
        assert len(restored.reserves) == 1
        assert len(restored.payments) == 1
        assert restored.total_incurred == claim.total_incurred

    def test_claim_with_documents_serialization(self):
        doc = ClaimDocument(
            document_type="fnol_report",
            storage_url="https://storage.example.com/fnol.pdf",
            uploaded_at=datetime.now(UTC),
        )
        claim = _make_claim(documents=[doc])
        data = claim.model_dump()
        assert len(data["documents"]) == 1
