"""Escalation queue API endpoints for OpenInsure.

Exposes the escalation queue so authorised users can review, approve, or
reject actions that exceeded the requesting user's authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.services import escalation

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ResolveRequest(BaseModel):
    """Payload for approving or rejecting an escalation."""

    resolved_by: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class EscalationResponse(BaseModel):
    """Public representation of an escalation item."""

    id: str
    action: str
    entity_type: str
    entity_id: str
    requested_by: str
    requested_role: str
    amount: float
    required_role: str
    escalation_chain: list[str]
    reason: str
    context: dict[str, Any]
    status: str
    created_at: str
    resolved_by: str | None
    resolved_at: str | None
    resolution_reason: str | None


class EscalationList(BaseModel):
    """List of escalation items."""

    items: list[EscalationResponse]
    total: int


class CountResponse(BaseModel):
    """Pending escalation count for dashboard badges."""

    pending: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/count", response_model=CountResponse)
async def escalation_count() -> CountResponse:
    """Return number of pending escalations (for dashboard badge)."""
    return CountResponse(pending=await escalation.count_pending())


@router.get("", response_model=EscalationList)
async def list_escalations(
    status: str | None = Query(None, description="Filter by status: pending, approved, rejected"),
    role: str | None = Query(None, description="Filter by required/escalation-chain role"),
) -> EscalationList:
    """List escalation items with optional filters."""
    items = await escalation.get_queue(status=status, role=role)
    return EscalationList(items=[EscalationResponse(**i) for i in items], total=len(items))


@router.get("/{item_id}", response_model=EscalationResponse)
async def get_escalation(item_id: str) -> EscalationResponse:
    """Retrieve a single escalation item."""
    item = await escalation.get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Escalation {item_id} not found")
    return EscalationResponse(**item)


@router.post("/{item_id}/approve", response_model=EscalationResponse)
async def approve_escalation(item_id: str, body: ResolveRequest) -> EscalationResponse:
    """Approve an escalation item."""
    item = await escalation.resolve(item_id, "approved", body.resolved_by, body.reason)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Escalation {item_id} not found")
    return EscalationResponse(**item)


@router.post("/{item_id}/reject", response_model=EscalationResponse)
async def reject_escalation(item_id: str, body: ResolveRequest) -> EscalationResponse:
    """Reject an escalation item."""
    item = await escalation.resolve(item_id, "rejected", body.resolved_by, body.reason)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Escalation {item_id} not found")
    return EscalationResponse(**item)
