"""Tests for domain events."""

from uuid import uuid4

from openinsure.domain.events import (
    AuditGenerated,
    ClaimClosed,
    ClaimPaid,
    ClaimReported,
    ClaimReserved,
    ComplianceAlert,
    DomainEvent,
    EventMetadata,
    PolicyBound,
    PolicyCancelled,
    PolicyEndorsed,
    PolicyRenewed,
    SubmissionQuoted,
    SubmissionReceived,
    SubmissionTriaged,
)


class TestCreateDomainEvent:
    """Test creating base domain events."""

    def test_create_domain_event(self):
        aggregate_id = uuid4()
        event = DomainEvent(
            event_type="test.event",
            aggregate_id=aggregate_id,
            aggregate_type="test",
        )
        assert event.event_type == "test.event"
        assert event.aggregate_id == aggregate_id
        assert event.aggregate_type == "test"
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_event_with_payload(self):
        event = DomainEvent(
            event_type="test.event",
            aggregate_id=uuid4(),
            aggregate_type="test",
            payload={"key": "value", "count": 42},
        )
        assert event.payload["key"] == "value"
        assert event.payload["count"] == 42

    def test_event_default_metadata(self):
        event = DomainEvent(
            event_type="test.event",
            aggregate_id=uuid4(),
            aggregate_type="test",
        )
        assert event.metadata is not None
        assert event.metadata.agent_id is None
        assert event.metadata.correlation_id is None


class TestSubmissionReceivedEvent:
    """Test SubmissionReceived event."""

    def test_submission_received_event(self):
        submission_id = uuid4()
        event = SubmissionReceived.create(
            submission_id=submission_id,
            payload={"channel": "email", "lob": "cyber"},
        )
        assert event.event_type == "submission.received"
        assert event.aggregate_id == submission_id
        assert event.aggregate_type == "submission"
        assert event.payload["channel"] == "email"

    def test_submission_received_no_payload(self):
        event = SubmissionReceived.create(submission_id=uuid4())
        assert event.payload == {}

    def test_submission_triaged_event(self):
        sub_id = uuid4()
        event = SubmissionTriaged.create(
            submission_id=sub_id,
            payload={"risk_score": 6.5, "priority": 2},
        )
        assert event.event_type == "submission.triaged"
        assert event.aggregate_id == sub_id

    def test_submission_quoted_event(self):
        sub_id = uuid4()
        event = SubmissionQuoted.create(
            submission_id=sub_id,
            payload={"premium": "15000.00"},
        )
        assert event.event_type == "submission.quoted"


class TestPolicyBoundEvent:
    """Test PolicyBound event."""

    def test_policy_bound_event(self):
        policy_id = uuid4()
        event = PolicyBound.create(
            policy_id=policy_id,
            payload={"policy_number": "POL-001", "premium": "15000.00"},
        )
        assert event.event_type == "policy.bound"
        assert event.aggregate_id == policy_id
        assert event.aggregate_type == "policy"
        assert event.payload["policy_number"] == "POL-001"

    def test_policy_endorsed_event(self):
        policy_id = uuid4()
        event = PolicyEndorsed.create(
            policy_id=policy_id,
            payload={"endorsement_number": "END-001"},
        )
        assert event.event_type == "policy.endorsed"

    def test_policy_renewed_event(self):
        event = PolicyRenewed.create(
            policy_id=uuid4(),
            payload={"renewal_number": "POL-R001"},
        )
        assert event.event_type == "policy.renewed"

    def test_policy_cancelled_event(self):
        event = PolicyCancelled.create(
            policy_id=uuid4(),
            payload={"reason": "Insured request"},
        )
        assert event.event_type == "policy.cancelled"


class TestClaimReportedEvent:
    """Test ClaimReported event."""

    def test_claim_reported_event(self):
        claim_id = uuid4()
        event = ClaimReported.create(
            claim_id=claim_id,
            payload={"cause_of_loss": "ransomware", "severity": "complex"},
        )
        assert event.event_type == "claim.reported"
        assert event.aggregate_id == claim_id
        assert event.aggregate_type == "claim"

    def test_claim_reserved_event(self):
        event = ClaimReserved.create(
            claim_id=uuid4(),
            payload={"amount": "50000.00"},
        )
        assert event.event_type == "claim.reserved"

    def test_claim_paid_event(self):
        event = ClaimPaid.create(
            claim_id=uuid4(),
            payload={"amount": "25000.00"},
        )
        assert event.event_type == "claim.paid"

    def test_claim_closed_event(self):
        event = ClaimClosed.create(
            claim_id=uuid4(),
            payload={"reason": "Settled"},
        )
        assert event.event_type == "claim.closed"


class TestEventSerialization:
    """Test event serialization."""

    def test_event_serialization(self):
        event = PolicyBound.create(
            policy_id=uuid4(),
            payload={"premium": "15000.00"},
        )
        data = event.model_dump()
        assert data["event_type"] == "policy.bound"
        assert "event_id" in data
        assert "timestamp" in data
        assert data["payload"]["premium"] == "15000.00"

    def test_event_roundtrip(self):
        original = ClaimReported.create(
            claim_id=uuid4(),
            payload={"severity": "complex"},
        )
        data = original.model_dump()
        restored = ClaimReported(**data)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.aggregate_id == original.aggregate_id

    def test_compliance_alert_event(self):
        agg_id = uuid4()
        event = ComplianceAlert.create(
            aggregate_id=agg_id,
            aggregate_type="policy",
            payload={"alert": "Regulatory filing required"},
        )
        assert event.event_type == "compliance.alert"
        assert event.aggregate_type == "policy"

    def test_audit_generated_event(self):
        event = AuditGenerated.create(
            aggregate_id=uuid4(),
            aggregate_type="submission",
            payload={"audit_type": "quarterly"},
        )
        assert event.event_type == "audit.generated"


class TestEventMetadata:
    """Test event metadata."""

    def test_event_metadata(self):
        correlation_id = uuid4()
        causation_id = uuid4()
        metadata = EventMetadata(
            agent_id="underwriting-agent",
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        assert metadata.agent_id == "underwriting-agent"
        assert metadata.correlation_id == correlation_id
        assert metadata.causation_id == causation_id

    def test_event_with_metadata(self):
        metadata = EventMetadata(agent_id="rating-agent")
        event = SubmissionReceived.create(
            submission_id=uuid4(),
            metadata=metadata,
        )
        assert event.metadata.agent_id == "rating-agent"

    def test_event_unique_ids(self):
        e1 = PolicyBound.create(policy_id=uuid4())
        e2 = PolicyBound.create(policy_id=uuid4())
        assert e1.event_id != e2.event_id
