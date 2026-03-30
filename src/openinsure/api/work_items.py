"""Work items API endpoints for OpenInsure.

Provides inbox-style work queues: list, complete, and query work items
assigned to users or roles.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.services import work_item_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class WorkItemCreate(BaseModel):
    """Payload for creating a work item."""

    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    work_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    assigned_to: str | None = None
    assigned_role: str | None = None
    priority: str = Field("medium", description="low, medium, high, urgent")
    due_date: str | None = None
    sla_hours: int | None = None


class CompleteRequest(BaseModel):
    """Payload for completing a work item."""

    completed_by: str = Field(..., min_length=1)


class WorkItemResponse(BaseModel):
    """Public representation of a work item."""

    id: str
    entity_type: str
    entity_id: str
    work_type: str
    title: str
    description: str | None = None
    assigned_to: str | None = None
    assigned_role: str | None = None
    priority: str = "medium"
    status: str = "open"
    due_date: str | None = None
    sla_hours: int | None = None
    completed_at: str | None = None
    completed_by: str | None = None
    created_at: str


class WorkItemList(BaseModel):
    """Paginated list of work items."""

    items: list[WorkItemResponse]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=WorkItemResponse, status_code=201)
async def create_work_item(body: WorkItemCreate) -> WorkItemResponse:
    """Create a new work item."""
    item = await work_item_service.create_work_item(
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        work_type=body.work_type,
        title=body.title,
        description=body.description,
        assigned_to=body.assigned_to,
        assigned_role=body.assigned_role,
        priority=body.priority,
        due_date=body.due_date,
        sla_hours=body.sla_hours,
    )
    return WorkItemResponse(**item)


@router.get("", response_model=WorkItemList)
async def list_work_items(
    assigned_to: str | None = Query(None, description="Filter by assigned user"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    status: str | None = Query(None, description="Filter by status"),
) -> WorkItemList:
    """List work items with optional filters."""
    # If assigned_to is provided without status, return inbox (open/in_progress)
    if assigned_to and not status and not entity_type and not entity_id:
        items = await work_item_service.get_inbox(assigned_to)
    else:
        items = await work_item_service.list_work_items(
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            assigned_to=assigned_to,
        )
    return WorkItemList(items=[WorkItemResponse(**i) for i in items], total=len(items))


@router.get("/{item_id}", response_model=WorkItemResponse)
async def get_work_item(item_id: str) -> WorkItemResponse:
    """Retrieve a single work item by ID."""
    item = await work_item_service.get_work_item_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id} not found")
    return WorkItemResponse(**item)


@router.post("/{item_id}/complete", response_model=WorkItemResponse)
async def complete_work_item(item_id: str, body: CompleteRequest) -> WorkItemResponse:
    """Mark a work item as completed."""
    try:
        item = await work_item_service.complete_work_item(item_id, body.completed_by)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id} not found")
    return WorkItemResponse(**item)
