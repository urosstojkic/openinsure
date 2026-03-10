"""Domain events API."""

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/recent")
async def get_recent_events(limit: int = Query(20, ge=1, le=100)) -> dict[str, object]:
    """Get recent domain events (from in-memory ring buffer)."""
    from openinsure.services.event_publisher import get_recent_events

    return {"items": get_recent_events(limit)}
