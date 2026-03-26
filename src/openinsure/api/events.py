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
