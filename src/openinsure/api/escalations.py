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
    """Paginated list of escalation items."""

    items: list[EscalationResponse]
    total: int
    skip: int
    limit: int


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
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> EscalationList:
    """List escalation items with optional filters."""
    items = await escalation.get_queue(status=status, role=role)
    total = len(items)
    page = items[skip : skip + limit]
    return EscalationList(
        items=[EscalationResponse(**i) for i in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{item_id}", response_model=EscalationResponse)
async def get_escalation(item_id: str) -> EscalationResponse:
    """Retrieve a single escalation item."""
    item = await escalation.get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Escalation {item_id} not found")
    return EscalationResponse(**item)


class CreateEscalationRequest(BaseModel):
    """Payload for manually creating an escalation (admin/testing)."""

    action: str = Field(..., description="Action type: quote, bind, reserve, settlement")
    entity_type: str = Field(..., description="Entity type: submission, claim")
    entity_id: str = Field(..., description="ID of the related entity")
    requested_by: str = Field(default="system", description="Who requested the action")
    requested_role: str = Field(default="openinsure-uw-analyst", description="Role of the requester")
    amount: float = Field(..., gt=0, description="Dollar amount that triggered the escalation")
    required_role: str = Field(default="openinsure-senior-uw", description="Role required for approval")
    reason: str = Field(default="Amount exceeds authority limit", description="Reason for escalation")
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("", response_model=EscalationResponse, status_code=201)
async def create_escalation(body: CreateEscalationRequest) -> EscalationResponse:
    """Manually create an escalation record (admin/testing use)."""
    item = await escalation.escalate(
        action=body.action,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        requested_by=body.requested_by,
        requested_role=body.requested_role,
        amount=body.amount,
        authority_result={
            "required_role": body.required_role,
            "escalation_chain": [body.required_role],
            "reason": body.reason,
        },
        context=body.context,
    )
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
