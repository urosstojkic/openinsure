"""Domain event publishing service.

Publishes events to Azure Event Grid when configured, and persists every
event to the ``domain_events`` SQL table (event store) for replay, ML
pipelines, and regulatory auditing.

Falls back to logging-only when event bus is not available.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import structlog

from openinsure.infrastructure.factory import get_database_adapter, get_event_bus

logger = structlog.get_logger()

_recent_events: list[dict[str, Any]] = []
_MAX_EVENTS = 100


def get_recent_events(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent domain events from the in-memory ring buffer."""
    return list(reversed(_recent_events[-limit:]))


def _parse_aggregate(subject: str, data: dict[str, Any]) -> tuple[str, str | None]:
    """Derive aggregate_type and aggregate_id from the event subject/data.

    Convention: subject looks like ``/submissions/{id}`` or
    ``/policies/{id}/endorsements``.  We take the first path segment as the
    aggregate type and the second as the aggregate ID (if it looks like a
    UUID).
    """
    parts = [p for p in subject.strip("/").split("/") if p]
    aggregate_type = parts[0] if parts else "unknown"

    # Try the second path segment first, then fall-back to data keys
    candidate: str | None = parts[1] if len(parts) > 1 else None
    if candidate:
        try:
            UUID(candidate)
            return aggregate_type, candidate
        except (ValueError, AttributeError):
            pass

    # Look for common ID keys inside data
    for key in ("id", "submission_id", "policy_id", "claim_id", "entity_id"):
        val = data.get(key)
        if val:
            try:
                UUID(str(val))
                return aggregate_type, str(val)
            except (ValueError, AttributeError):
                pass

    return aggregate_type, None


async def _persist_to_event_store(
    event_type: str,
    subject: str,
    data: dict[str, Any],
    *,
    correlation_id: str | None = None,
    actor: str | None = None,
    occurred_at: str | None = None,
) -> None:
    """Persist a domain event to the SQL event store (non-critical)."""
    db = get_database_adapter()
    if db is None:
        return

    aggregate_type, aggregate_id_str = _parse_aggregate(subject, data)
    if aggregate_id_str is None:
        # Cannot persist without an aggregate — skip silently
        return

    event_id = str(uuid4())
    payload = json.dumps(data, default=str)
    metadata = json.dumps({"correlation_id": correlation_id, "subject": subject}, default=str)

    try:
        # Use MAX(version)+1 for optimistic concurrency on the aggregate stream
        await db.execute_query(
            """
            INSERT INTO domain_events
                (event_id, event_type, aggregate_type, aggregate_id, version,
                 payload, metadata, actor)
            VALUES
                (?, ?, ?, ?, COALESCE(
                    (SELECT MAX(version) + 1 FROM domain_events
                     WHERE aggregate_id = ?), 1),
                 ?, ?, ?)
            """,
            [
                event_id,
                event_type,
                aggregate_type,
                aggregate_id_str,
                aggregate_id_str,
                payload,
                metadata,
                actor,
            ],
        )
        logger.debug("event_store.persisted", event_type=event_type, aggregate_id=aggregate_id_str)
    except Exception as exc:
        # Event persistence is non-critical — log and continue
        logger.warning("event_store.persist_failed", event_type=event_type, error=str(exc)[:200])


async def publish_domain_event(
    event_type: str,
    subject: str,
    data: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Publish a domain event. No-op if event bus not configured."""
    from datetime import UTC, datetime

    now_iso = datetime.now(UTC).isoformat()

    # Always record in ring buffer
    record = {
        "event_type": event_type,
        "subject": subject,
        "data": data,
        "timestamp": now_iso,
        "correlation_id": correlation_id,
    }
    _recent_events.append(record)
    if len(_recent_events) > _MAX_EVENTS:
        _recent_events[:] = _recent_events[-_MAX_EVENTS:]

    # Persist to SQL event store
    await _persist_to_event_store(event_type, subject, data, correlation_id=correlation_id, occurred_at=now_iso)

    bus = get_event_bus()
    if bus:
        try:
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


async def get_events_for_aggregate(
    aggregate_id: str,
    aggregate_type: str | None = None,
) -> list[dict[str, Any]]:
    """Replay persisted events for a given aggregate from the SQL event store.

    Falls back to filtering the in-memory ring buffer when SQL is not
    configured.
    """
    db = get_database_adapter()
    if db is not None:
        query = "SELECT * FROM domain_events WHERE aggregate_id = ?"
        params: list[Any] = [aggregate_id]
        if aggregate_type:
            query += " AND aggregate_type = ?"
            params.append(aggregate_type)
        query += " ORDER BY version ASC"
        rows = await db.fetch_all(query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            raw_meta = row.get("metadata")
            parsed_meta = json.loads(raw_meta) if isinstance(raw_meta, str) and raw_meta else raw_meta
            raw_occurred = row["occurred_at"]
            occurred_str = raw_occurred.isoformat() if hasattr(raw_occurred, "isoformat") else str(raw_occurred)
            entry: dict[str, Any] = {
                "id": row.get("id"),
                "event_id": str(row["event_id"]),
                "event_type": row["event_type"],
                "aggregate_type": row["aggregate_type"],
                "aggregate_id": str(row["aggregate_id"]),
                "version": row["version"],
                "payload": (json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]),
                "metadata": parsed_meta,
                "actor": row.get("actor"),
                "occurred_at": occurred_str,
            }
            results.append(entry)
        return results

    # Fallback: filter in-memory ring buffer
    return [e for e in _recent_events if any(str(v) == aggregate_id for v in e.get("data", {}).values())]
