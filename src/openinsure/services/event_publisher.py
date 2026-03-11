"""Domain event publishing service.

Publishes events to Azure Event Grid when configured.
Falls back to logging-only when event bus is not available.
"""

from __future__ import annotations

from typing import Any

import structlog

from openinsure.infrastructure.factory import get_event_bus

logger = structlog.get_logger()

_recent_events: list[dict[str, Any]] = []
_MAX_EVENTS = 100


def get_recent_events(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent domain events from the in-memory ring buffer."""
    return list(reversed(_recent_events[-limit:]))


async def publish_domain_event(
    event_type: str,
    subject: str,
    data: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Publish a domain event. No-op if event bus not configured."""
    from datetime import UTC, datetime

    # Always record in ring buffer
    record = {
        "event_type": event_type,
        "subject": subject,
        "data": data,
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": correlation_id,
    }
    _recent_events.append(record)
    if len(_recent_events) > _MAX_EVENTS:
        _recent_events[:] = _recent_events[-_MAX_EVENTS:]

    bus = get_event_bus()
    if bus:
        try:
            from uuid import UUID

            from openinsure.infrastructure.event_bus import DomainEvent

            event = DomainEvent(
                event_type=event_type,
                subject=subject,
                data=data,
                correlation_id=UUID(correlation_id) if correlation_id else None,
            )
            await bus.publish_event(event)
            logger.info("event.published", event_type=event_type, subject=subject)
        except Exception as e:
            # Event publishing is non-critical — log and continue
            logger.warning("event.publish_failed", event_type=event_type, error=str(e)[:200])
    else:
        logger.debug("event.skipped", event_type=event_type, subject=subject, reason="no_event_bus")
