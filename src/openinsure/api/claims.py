"""Claims API endpoints for OpenInsure.

Manages the claims lifecycle: FNOL → investigation → reserve → payment → close.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_claim_repository

router = APIRouter()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_claim_repository()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClaimStatus(StrEnum):
    """Lifecycle states for a claim."""

    REPORTED = "reported"
    UNDER_INVESTIGATION = "under_investigation"
    RESERVED = "reserved"
    APPROVED = "approved"
    DENIED = "denied"
    CLOSED = "closed"
    REOPENED = "reopened"


class ClaimType(StrEnum):
    """Types of cyber insurance claims."""

    DATA_BREACH = "data_breach"
    RANSOMWARE = "ransomware"
    BUSINESS_INTERRUPTION = "business_interruption"
    THIRD_PARTY_LIABILITY = "third_party_liability"
    REGULATORY_PROCEEDING = "regulatory_proceeding"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ClaimCreate(BaseModel):
    """First Notice of Loss (FNOL) payload."""

    policy_id: str
    claim_type: ClaimType
    description: str = Field(..., min_length=1)
    date_of_loss: str = Field(..., description="ISO-8601 date of the loss event")
    reported_by: str = Field(..., min_length=1, max_length=200)
    contact_email: str | None = None
    contact_phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimUpdate(BaseModel):
    """Payload for updating a claim."""

    description: str | None = None
    claim_type: ClaimType | None = None
    metadata: dict[str, Any] | None = None


class ClaimResponse(BaseModel):
    """Public representation of a claim."""

    id: str
    claim_number: str
    policy_id: str
    claim_type: ClaimType
    status: ClaimStatus
    description: str
    date_of_loss: str
    reported_by: str
    contact_email: str | None = None
    contact_phone: str | None = None
    reserves: list[dict[str, Any]]
    payments: list[dict[str, Any]]
    total_reserved: float
    total_paid: float
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class ClaimList(BaseModel):
    """Paginated list of claims."""

    items: list[ClaimResponse]
    total: int
    skip: int
    limit: int


class ReserveRequest(BaseModel):
    """Set or update a reserve on a claim."""

    category: str = Field(..., description="Reserve category, e.g. 'indemnity', 'expense'")
    amount: float = Field(..., ge=0)
    currency: str = "USD"
    notes: str | None = None


class ReserveResponse(BaseModel):
    """Result of setting/updating a reserve."""

    claim_id: str
    reserve_id: str
    category: str
    amount: float
    currency: str
    total_reserved: float
    created_at: str


class PaymentRequest(BaseModel):
    """Record a claim payment."""

    payee: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    category: str = Field(..., description="Payment category, e.g. 'indemnity', 'expense'")
    reference: str | None = None
    notes: str | None = None


class PaymentResponse(BaseModel):
    """Result of recording a payment."""

    claim_id: str
    payment_id: str
    payee: str
    amount: float
    currency: str
    category: str
    total_paid: float
    created_at: str


class CloseRequest(BaseModel):
    """Request to close a claim."""

    reason: str = Field(..., min_length=1)
    outcome: str = Field("resolved", description="Claim outcome summary")


class CloseResponse(BaseModel):
    """Result of closing a claim."""

    claim_id: str
    status: ClaimStatus
    reason: str
    outcome: str
    closed_at: str


class ReopenRequest(BaseModel):
    """Request to reopen a closed claim."""

    reason: str = Field(..., min_length=1)


class ReopenResponse(BaseModel):
    """Result of reopening a claim."""

    claim_id: str
    status: ClaimStatus
    reason: str
    reopened_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_claim(claim_id: str) -> dict[str, Any]:
    claim = await _repo.get_by_id(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return claim


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _generate_claim_number() -> str:
    return f"CLM-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ClaimResponse, status_code=201)
async def create_claim(body: ClaimCreate) -> ClaimResponse:
    """Report a new claim (First Notice of Loss)."""
    cid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": cid,
        "claim_number": _generate_claim_number(),
        "policy_id": body.policy_id,
        "claim_type": body.claim_type,
        "status": ClaimStatus.REPORTED,
        "description": body.description,
        "date_of_loss": body.date_of_loss,
        "reported_by": body.reported_by,
        "contact_email": body.contact_email,
        "contact_phone": body.contact_phone,
        "reserves": [],
        "payments": [],
        "total_reserved": 0.0,
        "total_paid": 0.0,
        "metadata": body.metadata,
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)
    return ClaimResponse(**record)


@router.get("", response_model=ClaimList)
async def list_claims(
    status: ClaimStatus | None = Query(None, description="Filter by claim status"),
    claim_type: ClaimType | None = Query(None, description="Filter by claim type"),
    policy_id: str | None = Query(None, description="Filter by policy ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ClaimList:
    """List claims with optional filtering and pagination."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if claim_type is not None:
        filters["claim_type"] = claim_type
    if policy_id is not None:
        filters["policy_id"] = policy_id

    total = await _repo.count(filters)
    page = await _repo.list_all(filters=filters, skip=skip, limit=limit)
    return ClaimList(
        items=[ClaimResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: str) -> ClaimResponse:
    """Retrieve a single claim by ID."""
    return ClaimResponse(**await _get_claim(claim_id))


@router.put("/{claim_id}", response_model=ClaimResponse)
async def update_claim(claim_id: str, body: ClaimUpdate) -> ClaimResponse:
    """Update a claim's mutable fields."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot update a closed claim; reopen it first")

    updates = body.model_dump(exclude_unset=True)
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    return ClaimResponse(**record)


@router.post("/{claim_id}/reserve", response_model=ReserveResponse, status_code=201)
async def set_reserve(claim_id: str, body: ReserveRequest) -> ReserveResponse:
    """Set or update reserves on a claim."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot set reserves on a closed claim")

    rid = str(uuid.uuid4())
    now = _now()
    reserve_entry: dict[str, Any] = {
        "reserve_id": rid,
        "category": body.category,
        "amount": body.amount,
        "currency": body.currency,
        "notes": body.notes,
        "created_at": now,
    }
    record["reserves"].append(reserve_entry)
    record["total_reserved"] = sum(r["amount"] for r in record["reserves"])
    if record["status"] == ClaimStatus.REPORTED:
        record["status"] = ClaimStatus.RESERVED
    record["updated_at"] = now

    return ReserveResponse(
        claim_id=claim_id,
        reserve_id=rid,
        category=body.category,
        amount=body.amount,
        currency=body.currency,
        total_reserved=record["total_reserved"],
        created_at=now,
    )


@router.post("/{claim_id}/payment", response_model=PaymentResponse, status_code=201)
async def record_payment(claim_id: str, body: PaymentRequest) -> PaymentResponse:
    """Record a payment against a claim."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot record payments on a closed claim")

    pid = str(uuid.uuid4())
    now = _now()
    payment_entry: dict[str, Any] = {
        "payment_id": pid,
        "payee": body.payee,
        "amount": body.amount,
        "currency": body.currency,
        "category": body.category,
        "reference": body.reference,
        "notes": body.notes,
        "created_at": now,
    }
    record["payments"].append(payment_entry)
    record["total_paid"] = sum(p["amount"] for p in record["payments"])
    if record["status"] in {ClaimStatus.REPORTED, ClaimStatus.RESERVED}:
        record["status"] = ClaimStatus.APPROVED
    record["updated_at"] = now

    return PaymentResponse(
        claim_id=claim_id,
        payment_id=pid,
        payee=body.payee,
        amount=body.amount,
        currency=body.currency,
        category=body.category,
        total_paid=record["total_paid"],
        created_at=now,
    )


@router.post("/{claim_id}/close", response_model=CloseResponse)
async def close_claim(claim_id: str, body: CloseRequest) -> CloseResponse:
    """Close a claim."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Claim is already closed")

    now = _now()
    record["status"] = ClaimStatus.CLOSED
    record["updated_at"] = now

    return CloseResponse(
        claim_id=claim_id,
        status=ClaimStatus.CLOSED,
        reason=body.reason,
        outcome=body.outcome,
        closed_at=now,
    )


@router.post("/{claim_id}/reopen", response_model=ReopenResponse)
async def reopen_claim(claim_id: str, body: ReopenRequest) -> ReopenResponse:
    """Reopen a previously closed claim."""
    record = await _get_claim(claim_id)
    if record["status"] != ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Only closed claims can be reopened")

    now = _now()
    record["status"] = ClaimStatus.REOPENED
    record["updated_at"] = now

    return ReopenResponse(
        claim_id=claim_id,
        status=ClaimStatus.REOPENED,
        reason=body.reason,
        reopened_at=now,
    )
