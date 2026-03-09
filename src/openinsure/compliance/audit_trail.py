"""Immutable Audit Trail for EU AI Act and insurance regulatory compliance.

Implements Art. 12 (Record-Keeping) and Art. 14 (Human Oversight) support.
Every system action is recorded with actor attribution, timestamps,
and correlation IDs for end-to-end traceability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ActorType(StrEnum):
    """Who or what performed the action."""

    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"


class AuditEvent(BaseModel):
    """A single immutable audit event."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str = Field(..., description="Category of event, e.g. 'quote.created', 'claim.approved'")
    actor_type: ActorType
    actor_id: str = Field(..., description="ID of the agent or human performing the action")
    resource_type: str = Field(..., description="Type of resource affected, e.g. 'policy', 'claim'")
    resource_id: str = Field(..., description="ID of the affected resource")
    action: str = Field(..., description="Verb describing the action, e.g. 'create', 'approve'")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured details about the event",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Shared ID linking related events across services",
    )

    model_config = {"frozen": True}


class AuditTrailStore:
    """In-memory append-only audit trail (replace with Event Hubs + Cosmos DB in production).

    Events are stored in insertion order and are never modified or deleted.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._index_by_resource: dict[str, list[int]] = {}
        self._index_by_actor: dict[str, list[int]] = {}

    async def record_event(self, event: AuditEvent) -> AuditEvent:
        """Append an event to the audit trail.

        Returns the recorded event (with server-assigned timestamp if needed).
        """
        idx = len(self._events)
        self._events.append(event)

        # Maintain resource and actor indexes for fast lookup
        resource_key = f"{event.resource_type}:{event.resource_id}"
        self._index_by_resource.setdefault(resource_key, []).append(idx)
        self._index_by_actor.setdefault(event.actor_id, []).append(idx)

        logger.info(
            "audit_trail.event_recorded",
            event_id=str(event.event_id),
            event_type=event.event_type,
            actor_id=event.actor_id,
            resource=resource_key,
        )
        return event

    async def get_events(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        event_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events with optional filtering.

        Filters are combined with AND semantics.
        """
        # Start with the narrowest index available
        if resource_type and resource_id:
            key = f"{resource_type}:{resource_id}"
            indices = self._index_by_resource.get(key, [])
            candidates = [self._events[i] for i in indices]
        elif actor_id:
            indices = self._index_by_actor.get(actor_id, [])
            candidates = [self._events[i] for i in indices]
        else:
            candidates = list(self._events)

        # Apply remaining filters
        results: list[AuditEvent] = []
        for evt in candidates:
            if resource_type and evt.resource_type != resource_type:
                continue
            if resource_id and evt.resource_id != resource_id:
                continue
            if actor_id and evt.actor_id != actor_id:
                continue
            if event_type and evt.event_type != event_type:
                continue
            if start_date and evt.timestamp < start_date:
                continue
            if end_date and evt.timestamp > end_date:
                continue
            results.append(evt)

        return results[offset : offset + limit]

    async def get_timeline(
        self,
        resource_type: str,
        resource_id: str,
        *,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Get the full chronological timeline for a specific resource.

        Returns events sorted by timestamp (oldest first).
        """
        key = f"{resource_type}:{resource_id}"
        indices = self._index_by_resource.get(key, [])
        events = [self._events[i] for i in indices]
        events.sort(key=lambda e: e.timestamp)
        return events[:limit]

    async def count(self) -> int:
        """Return total number of recorded events."""
        return len(self._events)
