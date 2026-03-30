"""Domain events API."""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter()


class RecentEventsResponse(BaseModel):
    """Response containing recent domain events."""

    items: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/recent", response_model=RecentEventsResponse)
async def get_recent_events(limit: int = Query(20, ge=1, le=100)) -> dict[str, object]:
    """Get recent domain events (from in-memory ring buffer)."""
    from openinsure.services.event_publisher import get_recent_events

    return {"items": get_recent_events(limit)}


class EventReplayResponse(BaseModel):
    """Response containing replayed events for an aggregate."""

    aggregate_id: str
    aggregate_type: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


@router.get("", response_model=EventReplayResponse)
async def replay_events(
    aggregate_id: str = Query(..., description="UUID of the aggregate to replay events for"),
    aggregate_type: str | None = Query(None, description="Optional aggregate type filter"),
) -> EventReplayResponse:
    """Replay persisted domain events for a given aggregate.

    Returns all events in version order for reconstructing aggregate state,
    feeding ML models, or regulatory audit.
    """
    from openinsure.services.event_publisher import get_events_for_aggregate

    events = await get_events_for_aggregate(aggregate_id, aggregate_type)
    return EventReplayResponse(
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        events=events,
        count=len(events),
    )
