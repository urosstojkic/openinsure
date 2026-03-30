"""Claim aggregate root.

Encapsulates all state transitions and domain invariants for
the claim lifecycle. Emits domain events on every mutation.
"""

from __future__ import annotations

from typing import Any

from openinsure.domain.events import (
    ClaimClosed,
    ClaimPaid,
    ClaimReported,
    ClaimReserved,
    DomainEvent,
    EventMetadata,
)
from openinsure.domain.state_machine import (
    validate_claim_invariants,
    validate_claim_transition,
)


class ClaimDenied(DomainEvent):
    """Emitted when a claim is denied."""

    @classmethod
    def create(
        cls,
        claim_id: Any,
        payload: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
    ) -> ClaimDenied:
        from uuid import UUID

        cid = claim_id if isinstance(claim_id, UUID) else UUID(str(claim_id))
        return cls(
            event_type="claim.denied",
            aggregate_id=cid,
            aggregate_type="claim",
            payload=payload or {},
            metadata=metadata or EventMetadata(),
        )


class ClaimAggregate:
    """Aggregate root for the Claim bounded context.

    Owns all claim state transitions and enforces invariants
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
        return str(self._data.get("status", "reported"))

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

    def report(self) -> None:
        """Mark claim as reported (FNOL)."""
        self._events.append(
            ClaimReported.create(
                self.id,
                payload={"claim_id": self.id},
            )
        )

    def investigate(self) -> None:
        """Move to investigation."""
        self._transition_to("investigating")

    def set_reserve(self, reserve: dict[str, Any]) -> None:
        """Set or adjust a reserve on the claim."""
        validate_claim_invariants(self._data)
        amount = reserve.get("amount", 0)
        if float(amount) < 0:
            raise ValueError("Reserve amount cannot be negative")
        self._transition_to("reserved")
        reserves = list(self._data.get("reserves", []))
        reserves.append(reserve)
        self._data["reserves"] = reserves
        self._events.append(
            ClaimReserved.create(
                self.id,
                payload={"claim_id": self.id, "reserve": reserve},
            )
        )

    def make_payment(self, payment: dict[str, Any]) -> None:
        """Record a payment on the claim."""
        self._transition_to("settling")
        payments = list(self._data.get("payments", []))
        payments.append(payment)
        self._data["payments"] = payments
        self._events.append(
            ClaimPaid.create(
                self.id,
                payload={"claim_id": self.id, "payment": payment},
            )
        )

    def deny(self, reason: str) -> None:
        """Deny the claim."""
        self._transition_to("denied")
        self._events.append(
            ClaimDenied.create(
                self.id,
                payload={"claim_id": self.id, "reason": reason},
            )
        )

    def close(self, reason: str = "") -> None:
        """Close the claim."""
        self._transition_to("closed")
        self._data["close_reason"] = reason
        self._events.append(
            ClaimClosed.create(
                self.id,
                payload={"claim_id": self.id, "reason": reason},
            )
        )

    # -- Internal helpers ----------------------------------------------------

    def _transition_to(self, target: str) -> None:
        current = self.status
        validate_claim_transition(current, target)
        self._data["status"] = target
