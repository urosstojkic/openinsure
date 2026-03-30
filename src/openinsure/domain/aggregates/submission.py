"""Submission aggregate root.

Encapsulates all state transitions and domain invariants for
the submission lifecycle. Emits domain events on every mutation.
"""

from __future__ import annotations

from typing import Any

from openinsure.domain.events import (
    DomainEvent,
    EventMetadata,
    SubmissionQuoted,
    SubmissionReceived,
    SubmissionTriaged,
)
from openinsure.domain.state_machine import (
    validate_submission_invariants,
    validate_submission_transition,
)


class SubmissionBound(DomainEvent):
    """Emitted when a submission is bound to a policy.

    Downstream handlers listen for this event to create the policy,
    billing account, and reinsurance cessions — each in its own
    aggregate boundary.
    """

    @classmethod
    def create(
        cls,
        submission_id: Any,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> SubmissionBound:
        from uuid import UUID

        sid = submission_id if isinstance(submission_id, UUID) else UUID(str(submission_id))
        return cls(
            event_type="submission.bound",
            aggregate_id=sid,
            aggregate_type="submission",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class SubmissionDeclined(DomainEvent):
    """Emitted when a submission is declined."""

    @classmethod
    def create(
        cls,
        submission_id: Any,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> SubmissionDeclined:
        from uuid import UUID

        sid = submission_id if isinstance(submission_id, UUID) else UUID(str(submission_id))
        return cls(
            event_type="submission.declined",
            aggregate_id=sid,
            aggregate_type="submission",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class SubmissionAggregate:
    """Aggregate root for the Submission bounded context.

    Owns all submission state transitions and enforces invariants
    before allowing mutations. Collects domain events that should be
    dispatched after the aggregate is persisted.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = dict(data)
        self._events: list[DomainEvent] = []

    # -- Read access ---------------------------------------------------------

    @property
    def id(self) -> str:
        return str(self._data.get("id", ""))

    @property
    def status(self) -> str:
        return str(self._data.get("status", "received"))

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def pending_events(self) -> list[DomainEvent]:
        """Return domain events that have not yet been dispatched."""
        return list(self._events)

    def clear_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events

    # -- State transitions ---------------------------------------------------

    def receive(self) -> None:
        """Mark the submission as received."""
        self._transition_to("received")
        self._events.append(
            SubmissionReceived.create(
                self.id,
                payload={"submission_id": self.id},
            )
        )

    def triage(self, triage_result: dict[str, Any] | None = None) -> None:
        """Advance to underwriting after triage."""
        self._transition_to("underwriting")
        self._data["triage_result"] = triage_result
        self._events.append(
            SubmissionTriaged.create(
                self.id,
                payload={"submission_id": self.id, "triage_result": triage_result},
            )
        )

    def quote(self, premium: float) -> None:
        """Set quoted premium and advance to quoted."""
        if premium <= 0:
            raise ValueError("Premium must be positive")
        self._transition_to("quoted")
        self._data["quoted_premium"] = premium
        self._events.append(
            SubmissionQuoted.create(
                self.id,
                payload={"submission_id": self.id, "premium": premium},
            )
        )

    def bind(self, policy_id: str, policy_number: str, premium: float) -> None:
        """Mark as bound. Emits ``SubmissionBound`` for downstream handlers.

        Does NOT create the policy — that is the responsibility of the
        ``PolicyCreationHandler`` listening for this event.
        """
        validate_submission_invariants(self._data)
        self._transition_to("bound")
        self._events.append(
            SubmissionBound.create(
                self.id,
                payload={
                    "submission_id": self.id,
                    "policy_id": policy_id,
                    "policy_number": policy_number,
                    "premium": premium,
                },
            )
        )

    def decline(self, reason: str = "") -> None:
        """Decline the submission."""
        self._transition_to("declined")
        self._events.append(
            SubmissionDeclined.create(
                self.id,
                payload={"submission_id": self.id, "reason": reason},
            )
        )

    # -- Internal helpers ----------------------------------------------------

    def _transition_to(self, target: str) -> None:
        """Validate and apply a state transition."""
        current = self.status
        validate_submission_transition(current, target)
        self._data["status"] = target
