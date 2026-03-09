"""Domain events for OpenInsure event-driven architecture.

Provides a base ``DomainEvent`` model and concrete event classes for
key domain state transitions across submissions, policies, claims,
compliance, and auditing.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from openinsure.domain.common import new_id, utc_now


class EventMetadata(BaseModel):
    """Metadata attached to every domain event for tracing and correlation."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    agent_id: str | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


class DomainEvent(BaseModel):
    """Base class for all domain events.

    Every event carries an identity, timestamp, aggregate reference,
    payload, and tracing metadata.
    """

    model_config = ConfigDict(
        frozen=False,
        str_strip_whitespace=True,
    )

    event_id: UUID = Field(default_factory=new_id)
    event_type: str
    timestamp: datetime = Field(default_factory=utc_now)
    aggregate_id: UUID
    aggregate_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: EventMetadata = Field(default_factory=EventMetadata)


# ---------------------------------------------------------------------------
# Submission events
# ---------------------------------------------------------------------------


class SubmissionReceived(DomainEvent):
    """Emitted when a new submission is received."""

    @classmethod
    def create(
        cls,
        submission_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "SubmissionReceived":
        """Create a SubmissionReceived event."""
        return cls(
            event_type="submission.received",
            aggregate_id=submission_id,
            aggregate_type="submission",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class SubmissionTriaged(DomainEvent):
    """Emitted when a submission has been triaged."""

    @classmethod
    def create(
        cls,
        submission_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "SubmissionTriaged":
        """Create a SubmissionTriaged event."""
        return cls(
            event_type="submission.triaged",
            aggregate_id=submission_id,
            aggregate_type="submission",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class SubmissionQuoted(DomainEvent):
    """Emitted when a submission receives a premium quote."""

    @classmethod
    def create(
        cls,
        submission_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "SubmissionQuoted":
        """Create a SubmissionQuoted event."""
        return cls(
            event_type="submission.quoted",
            aggregate_id=submission_id,
            aggregate_type="submission",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


# ---------------------------------------------------------------------------
# Policy events
# ---------------------------------------------------------------------------


class PolicyBound(DomainEvent):
    """Emitted when a policy is bound."""

    @classmethod
    def create(
        cls,
        policy_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "PolicyBound":
        """Create a PolicyBound event."""
        return cls(
            event_type="policy.bound",
            aggregate_id=policy_id,
            aggregate_type="policy",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class PolicyEndorsed(DomainEvent):
    """Emitted when a policy endorsement is applied."""

    @classmethod
    def create(
        cls,
        policy_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "PolicyEndorsed":
        """Create a PolicyEndorsed event."""
        return cls(
            event_type="policy.endorsed",
            aggregate_id=policy_id,
            aggregate_type="policy",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class PolicyRenewed(DomainEvent):
    """Emitted when a policy is renewed."""

    @classmethod
    def create(
        cls,
        policy_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "PolicyRenewed":
        """Create a PolicyRenewed event."""
        return cls(
            event_type="policy.renewed",
            aggregate_id=policy_id,
            aggregate_type="policy",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class PolicyCancelled(DomainEvent):
    """Emitted when a policy is cancelled."""

    @classmethod
    def create(
        cls,
        policy_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "PolicyCancelled":
        """Create a PolicyCancelled event."""
        return cls(
            event_type="policy.cancelled",
            aggregate_id=policy_id,
            aggregate_type="policy",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


# ---------------------------------------------------------------------------
# Claim events
# ---------------------------------------------------------------------------


class ClaimReported(DomainEvent):
    """Emitted when a new claim is reported (FNOL)."""

    @classmethod
    def create(
        cls,
        claim_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "ClaimReported":
        """Create a ClaimReported event."""
        return cls(
            event_type="claim.reported",
            aggregate_id=claim_id,
            aggregate_type="claim",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class ClaimReserved(DomainEvent):
    """Emitted when reserves are set or adjusted on a claim."""

    @classmethod
    def create(
        cls,
        claim_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "ClaimReserved":
        """Create a ClaimReserved event."""
        return cls(
            event_type="claim.reserved",
            aggregate_id=claim_id,
            aggregate_type="claim",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class ClaimPaid(DomainEvent):
    """Emitted when a payment is issued on a claim."""

    @classmethod
    def create(
        cls,
        claim_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "ClaimPaid":
        """Create a ClaimPaid event."""
        return cls(
            event_type="claim.paid",
            aggregate_id=claim_id,
            aggregate_type="claim",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class ClaimClosed(DomainEvent):
    """Emitted when a claim is closed."""

    @classmethod
    def create(
        cls,
        claim_id: UUID,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "ClaimClosed":
        """Create a ClaimClosed event."""
        return cls(
            event_type="claim.closed",
            aggregate_id=claim_id,
            aggregate_type="claim",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


# ---------------------------------------------------------------------------
# Compliance and audit events
# ---------------------------------------------------------------------------


class ComplianceAlert(DomainEvent):
    """Emitted when a compliance issue is detected."""

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        aggregate_type: str,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "ComplianceAlert":
        """Create a ComplianceAlert event."""
        return cls(
            event_type="compliance.alert",
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class AuditGenerated(DomainEvent):
    """Emitted when an audit report is generated."""

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        aggregate_type: str,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> "AuditGenerated":
        """Create an AuditGenerated event."""
        return cls(
            event_type="audit.generated",
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )
