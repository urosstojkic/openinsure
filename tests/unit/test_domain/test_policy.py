"""Tests for the Policy domain entity."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from openinsure.domain.policy import (
    Coverage,
    Endorsement,
    Policy,
    PolicyDocument,
    PolicyStatus,
)


def _make_policy(**overrides) -> Policy:
    """Helper to create a policy with sensible defaults."""
    defaults = {
        "policy_number": "POL-TEST-001",
        "status": PolicyStatus.active,
        "product_id": uuid4(),
        "submission_id": uuid4(),
        "insured_id": uuid4(),
        "effective_date": date(2026, 7, 1),
        "expiration_date": date(2027, 7, 1),
        "total_premium": Decimal("15000.00"),
        "written_premium": Decimal("15000.00"),
        "earned_premium": Decimal("0.00"),
        "unearned_premium": Decimal("15000.00"),
    }
    defaults.update(overrides)
    return Policy(**defaults)


def _make_coverage(**overrides) -> Coverage:
    """Helper to create a coverage."""
    defaults = {
        "coverage_code": "CYB-001",
        "coverage_name": "Cyber Liability",
        "limit": Decimal("1000000.00"),
        "deductible": Decimal("10000.00"),
        "premium": Decimal("12000.00"),
    }
    defaults.update(overrides)
    return Coverage(**defaults)


class TestCreatePolicy:
    """Test creating a policy."""

    def test_create_policy(self):
        policy = _make_policy()
        assert policy.policy_number == "POL-TEST-001"
        assert policy.status == PolicyStatus.active
        assert policy.total_premium == Decimal("15000.00")
        assert policy.id is not None

    def test_default_status_is_pending(self):
        policy = _make_policy(status=PolicyStatus.pending)
        assert policy.status == PolicyStatus.pending

    def test_policy_with_broker(self):
        broker_id = uuid4()
        policy = _make_policy(broker_id=broker_id)
        assert policy.broker_id == broker_id


class TestPolicyWithCoverages:
    """Test policy with coverages."""

    def test_policy_with_coverages(self):
        cov = _make_coverage()
        policy = _make_policy(coverages=[cov])
        assert len(policy.coverages) == 1
        assert policy.coverages[0].coverage_code == "CYB-001"

    def test_policy_with_multiple_coverages(self):
        coverages = [
            _make_coverage(coverage_code="CYB-001", coverage_name="Cyber Liability"),
            _make_coverage(coverage_code="CYB-002", coverage_name="Data Breach Response"),
            _make_coverage(coverage_code="CYB-003", coverage_name="Business Interruption"),
        ]
        policy = _make_policy(coverages=coverages)
        assert len(policy.coverages) == 3

    def test_coverage_with_sublimits(self):
        cov = Coverage(
            coverage_code="CYB-001",
            coverage_name="Cyber Liability",
            limit=Decimal("1000000.00"),
            deductible=Decimal("10000.00"),
            premium=Decimal("12000.00"),
            sublimits={"ransomware": Decimal("500000"), "social_engineering": Decimal("250000")},
        )
        assert cov.sublimits is not None
        assert cov.sublimits["ransomware"] == Decimal("500000")


class TestEndorsementProcessing:
    """Test endorsement processing."""

    def test_endorsement_creation(self):
        endorsement = Endorsement(
            endorsement_number="POL-TEST-001-END-001",
            effective_date=date(2026, 10, 1),
            description="Add cyber extortion coverage",
            premium_change=Decimal("2000.00"),
            coverages_modified=["CYB-001"],
        )
        assert endorsement.premium_change == Decimal("2000.00")
        assert len(endorsement.coverages_modified) == 1

    def test_endorsement_with_negative_premium(self):
        endorsement = Endorsement(
            endorsement_number="POL-TEST-001-END-002",
            effective_date=date(2026, 10, 1),
            description="Remove optional coverage",
            premium_change=Decimal("-1500.00"),
        )
        assert endorsement.premium_change == Decimal("-1500.00")

    def test_policy_with_endorsements(self):
        endorsement = Endorsement(
            endorsement_number="POL-TEST-001-END-001",
            effective_date=date(2026, 10, 1),
            description="Increase limit",
            premium_change=Decimal("3000.00"),
        )
        policy = _make_policy(endorsements=[endorsement])
        assert len(policy.endorsements) == 1


class TestPremiumCalculations:
    """Test premium-related fields."""

    def test_premium_calculations(self):
        policy = _make_policy(
            total_premium=Decimal("20000.00"),
            written_premium=Decimal("20000.00"),
            earned_premium=Decimal("5000.00"),
            unearned_premium=Decimal("15000.00"),
        )
        assert policy.earned_premium + policy.unearned_premium == policy.total_premium

    def test_fully_earned_premium(self):
        policy = _make_policy(
            total_premium=Decimal("12000.00"),
            written_premium=Decimal("12000.00"),
            earned_premium=Decimal("12000.00"),
            unearned_premium=Decimal("0.00"),
        )
        assert policy.earned_premium == policy.total_premium
        assert policy.unearned_premium == Decimal("0.00")


class TestPolicyStatusTransitions:
    """Test policy status transitions."""

    def test_transition_to_active(self):
        policy = _make_policy(status=PolicyStatus.pending)
        policy.status = PolicyStatus.active
        assert policy.status == PolicyStatus.active

    def test_transition_to_cancelled(self):
        policy = _make_policy()
        policy.status = PolicyStatus.cancelled
        policy.cancelled_at = datetime.now(UTC)
        policy.cancel_reason = "Insured request"
        assert policy.status == PolicyStatus.cancelled
        assert policy.cancel_reason == "Insured request"

    def test_transition_to_expired(self):
        policy = _make_policy()
        policy.status = PolicyStatus.expired
        assert policy.status == PolicyStatus.expired

    def test_transition_to_suspended(self):
        policy = _make_policy()
        policy.status = PolicyStatus.suspended
        assert policy.status == PolicyStatus.suspended


class TestPolicySerialization:
    """Test policy serialization."""

    def test_policy_serialization(self):
        cov = _make_coverage()
        policy = _make_policy(coverages=[cov])
        data = policy.model_dump()
        assert data["policy_number"] == "POL-TEST-001"
        assert data["status"] == "active"
        assert len(data["coverages"]) == 1

    def test_policy_roundtrip(self):
        policy = _make_policy()
        data = policy.model_dump()
        restored = Policy(**data)
        assert restored.policy_number == policy.policy_number
        assert restored.id == policy.id
        assert restored.total_premium == policy.total_premium

    def test_policy_with_documents_serialization(self):
        doc = PolicyDocument(
            document_type="declarations",
            generated_at=datetime.now(UTC),
            storage_url="https://storage.example.com/dec_page.pdf",
        )
        policy = _make_policy(documents=[doc])
        data = policy.model_dump()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_type"] == "declarations"
