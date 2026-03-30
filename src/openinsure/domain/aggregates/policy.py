"""Policy aggregate root.

Encapsulates all state transitions and domain invariants for
the policy lifecycle. Emits domain events on every mutation.
"""

from __future__ import annotations

from typing import Any

from openinsure.domain.events import (
    DomainEvent,
    EventMetadata,
    PolicyBound,
    PolicyCancelled,
    PolicyEndorsed,
    PolicyRenewed,
)
from openinsure.domain.state_machine import (
    validate_policy_invariants,
    validate_policy_transition,
)


class PolicyActivated(DomainEvent):
    """Emitted when a policy transitions to active status."""

    @classmethod
    def create(
        cls,
        policy_id: Any,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> PolicyActivated:
        from uuid import UUID

        pid = policy_id if isinstance(policy_id, UUID) else UUID(str(policy_id))
        return cls(
            event_type="policy.activated",
            aggregate_id=pid,
            aggregate_type="policy",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class PolicyAggregate:
    """Aggregate root for the Policy bounded context.

    Owns all policy state transitions and enforces invariants
    before allowing mutations. Collects domain events that should
    be dispatched after the aggregate is persisted.
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
        return str(self._data.get("status", "pending"))

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def pending_events(self) -> list[DomainEvent]:
        return list(self._events)

    def clear_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    # -- State transitions ---------------------------------------------------

    def activate(self) -> None:
        """Activate the policy (e.g. after binding)."""
        validate_policy_invariants(self._data)
        self._transition_to("active")
        self._events.append(
            PolicyActivated.create(
                self.id,
                payload={"policy_id": self.id},
            )
        )

    def bind(self, submission_id: str, premium: float) -> None:
        """Record the policy as bound. Emits ``PolicyBound``."""
        validate_policy_invariants(self._data)
        self._data["status"] = "active"
        self._events.append(
            PolicyBound.create(
                self.id,
                payload={
                    "policy_id": self.id,
                    "policy_number": self._data.get("policy_number", ""),
                    "premium": premium,
                    "submission_id": submission_id,
                },
            )
        )

    def endorse(self, endorsement: dict[str, Any]) -> None:
        """Apply an endorsement. Policy must be active."""
        if self.status != "active":
            from openinsure.domain.state_machine import InvalidTransitionError

            raise InvalidTransitionError("Policy", self.status, "endorsed", "Policy must be active to endorse")
        endorsements = list(self._data.get("endorsements", []))
        endorsements.append(endorsement)
        self._data["endorsements"] = endorsements
        self._events.append(
            PolicyEndorsed.create(
                self.id,
                payload={"policy_id": self.id, "endorsement": endorsement},
            )
        )

    def renew(self, new_policy_id: str) -> None:
        """Mark this policy as renewed."""
        self._events.append(
            PolicyRenewed.create(
                self.id,
                payload={"policy_id": self.id, "new_policy_id": new_policy_id},
            )
        )

    def cancel(self, reason: str) -> None:
        """Cancel the policy."""
        self._transition_to("cancelled")
        self._data["cancel_reason"] = reason
        self._events.append(
            PolicyCancelled.create(
                self.id,
                payload={"policy_id": self.id, "reason": reason},
            )
        )

    # -- Internal helpers ----------------------------------------------------

    def _transition_to(self, target: str) -> None:
        current = self.status
        validate_policy_transition(current, target)
        self._data["status"] = target
