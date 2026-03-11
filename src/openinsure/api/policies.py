"""Policy API endpoints for OpenInsure.

Manages the full policy lifecycle: issuance → endorsement → renewal → cancellation.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_policy_repository

router = APIRouter()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_policy_repository()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyStatus(StrEnum):
    """Lifecycle states for a policy."""

    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    RENEWED = "renewed"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    """Payload for creating a new policy."""

    submission_id: str
    product_id: str
    policyholder_name: str = Field(..., min_length=1, max_length=200)
    effective_date: str = Field(..., description="ISO-8601 date")
    expiration_date: str = Field(..., description="ISO-8601 date")
    premium: float = Field(..., gt=0)
    coverages: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyUpdate(BaseModel):
    """Payload for updating policy mutable fields."""

    policyholder_name: str | None = None
    metadata: dict[str, Any] | None = None


class PolicyResponse(BaseModel):
    """Public representation of a policy."""

    id: str = ""
    submission_id: str = ""
    product_id: str = ""
    policy_number: str = ""
    policyholder_name: str = ""
    status: str = "active"
    effective_date: str = ""
    expiration_date: str = ""
    premium: float | None = None
    total_premium: float | None = None
    written_premium: float | None = None
    earned_premium: float | None = None
    unearned_premium: float | None = None
    coverages: list[dict[str, Any]] = Field(default_factory=list)
    endorsements: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    documents: list[str] = Field(default_factory=list)
    bound_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


class PolicyList(BaseModel):
    """Paginated list of policies."""

    items: list[PolicyResponse]
    total: int
    skip: int
    limit: int


class EndorsementRequest(BaseModel):
    """Request to create an endorsement on a policy."""

    description: str = Field(..., min_length=1)
    changes: dict[str, Any] = Field(default_factory=dict)
    effective_date: str = Field(..., description="ISO-8601 date")
    premium_delta: float = 0.0


class EndorsementResponse(BaseModel):
    """Result of an endorsement."""

    policy_id: str
    endorsement_id: str
    description: str
    changes: dict[str, Any]
    effective_date: str
    premium_delta: float
    created_at: str


class RenewalResponse(BaseModel):
    """Result of initiating a renewal."""

    policy_id: str
    renewal_policy_id: str
    status: PolicyStatus
    new_effective_date: str
    new_expiration_date: str


class CancelRequest(BaseModel):
    """Request to cancel a policy."""

    reason: str = Field(..., min_length=1)
    cancellation_date: str = Field(..., description="ISO-8601 effective cancellation date")


class CancelResponse(BaseModel):
    """Result of cancelling a policy."""

    policy_id: str
    status: PolicyStatus
    reason: str
    cancellation_date: str
    cancelled_at: str


class DocumentItem(BaseModel):
    """A policy document reference."""

    document_id: str
    name: str
    type: str


class PolicyDocumentList(BaseModel):
    """List of documents attached to a policy."""

    policy_id: str
    documents: list[DocumentItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_policy(policy_id: str) -> dict[str, Any]:
    policy = await _repo.get_by_id(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _generate_policy_number() -> str:
    return f"POL-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(body: PolicyCreate) -> PolicyResponse:
    """Create a policy (typically from binding a submission)."""
    pid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": pid,
        "submission_id": body.submission_id,
        "product_id": body.product_id,
        "policy_number": _generate_policy_number(),
        "policyholder_name": body.policyholder_name,
        "status": PolicyStatus.ACTIVE,
        "effective_date": body.effective_date,
        "expiration_date": body.expiration_date,
        "premium": body.premium,
        "coverages": body.coverages,
        "endorsements": [],
        "metadata": body.metadata,
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)
    return PolicyResponse(**record)


@router.get("", response_model=PolicyList)
async def list_policies(
    status: PolicyStatus | None = Query(None, description="Filter by policy status"),
    policyholder: str | None = Query(None, description="Filter by policyholder name (substring)"),
    product_id: str | None = Query(None, description="Filter by product ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PolicyList:
    """List policies with optional filtering and pagination."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if policyholder is not None:
        filters["policyholder_name__contains"] = policyholder
    if product_id is not None:
        filters["product_id"] = product_id

    total = await _repo.count(filters)
    page = await _repo.list_all(filters=filters, skip=skip, limit=limit)
    return PolicyList(
        items=[PolicyResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str) -> PolicyResponse:
    """Retrieve a single policy by ID."""
    return PolicyResponse(**await _get_policy(policy_id))


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(policy_id: str, body: PolicyUpdate) -> PolicyResponse:
    """Update a policy's mutable fields."""
    record = await _get_policy(policy_id)
    if record["status"] == PolicyStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Cannot update a cancelled policy")

    updates = body.model_dump(exclude_unset=True)
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    return PolicyResponse(**record)


@router.post("/{policy_id}/endorse", response_model=EndorsementResponse, status_code=201)
async def endorse_policy(policy_id: str, body: EndorsementRequest) -> EndorsementResponse:
    """Create an endorsement (mid-term change) on a policy."""
    record = await _get_policy(policy_id)
    if record["status"] != PolicyStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Endorsements require an active policy")

    eid = str(uuid.uuid4())
    now = _now()
    endorsement: dict[str, Any] = {
        "endorsement_id": eid,
        "description": body.description,
        "changes": body.changes,
        "effective_date": body.effective_date,
        "premium_delta": body.premium_delta,
        "created_at": now,
    }
    record["endorsements"].append(endorsement)
    record["premium"] += body.premium_delta
    record["updated_at"] = now

    return EndorsementResponse(policy_id=policy_id, **endorsement)


@router.post("/{policy_id}/renew", response_model=RenewalResponse, status_code=201)
async def renew_policy(policy_id: str) -> RenewalResponse:
    """Initiate a renewal for an active or expiring policy.

    Creates a new policy record with updated effective/expiration dates.
    """
    record = await _get_policy(policy_id)
    if record["status"] not in {PolicyStatus.ACTIVE, PolicyStatus.EXPIRED}:
        raise HTTPException(status_code=409, detail="Only active or expired policies can be renewed")

    # Mark original as renewed
    record["status"] = PolicyStatus.RENEWED
    record["updated_at"] = _now()

    # Create renewal policy
    new_pid = str(uuid.uuid4())
    now = _now()
    new_effective = record["expiration_date"]
    # Stub: add 1 year
    new_expiration = new_effective.replace(new_effective[:4], str(int(new_effective[:4]) + 1), 1)
    renewal: dict[str, Any] = {
        **record,
        "id": new_pid,
        "policy_number": _generate_policy_number(),
        "status": PolicyStatus.ACTIVE,
        "effective_date": new_effective,
        "expiration_date": new_expiration,
        "endorsements": [],
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(renewal)

    return RenewalResponse(
        policy_id=policy_id,
        renewal_policy_id=new_pid,
        status=PolicyStatus.ACTIVE,
        new_effective_date=new_effective,
        new_expiration_date=new_expiration,
    )


@router.post("/{policy_id}/cancel", response_model=CancelResponse)
async def cancel_policy(policy_id: str, body: CancelRequest) -> CancelResponse:
    """Cancel an active policy."""
    record = await _get_policy(policy_id)
    if record["status"] != PolicyStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Only active policies can be cancelled")

    record["status"] = PolicyStatus.CANCELLED
    now = _now()
    record["updated_at"] = now

    return CancelResponse(
        policy_id=policy_id,
        status=PolicyStatus.CANCELLED,
        reason=body.reason,
        cancellation_date=body.cancellation_date,
        cancelled_at=now,
    )


@router.get("/{policy_id}/documents", response_model=PolicyDocumentList)
async def list_policy_documents(policy_id: str) -> PolicyDocumentList:
    """List documents attached to a policy.

    Stub — returns placeholder documents based on the IDs stored on the policy.
    """
    record = await _get_policy(policy_id)
    docs = [
        DocumentItem(document_id=did, name=f"document-{did[:8]}", type="application/pdf") for did in record["documents"]
    ]
    return PolicyDocumentList(policy_id=policy_id, documents=docs)
