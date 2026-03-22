"""Reinsurance API endpoints for OpenInsure.

Carrier-only module — disabled in MGA deployments via deployment profile.
Manages reinsurance treaties, cessions, recoveries, and bordereau generation.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import (
    get_cession_repository,
    get_recovery_repository,
    get_reinsurance_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Repositories — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_treaty_repo = get_reinsurance_repository()
_cession_repo = get_cession_repository()
_recovery_repo = get_recovery_repository()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TreatyCreate(BaseModel):
    """Payload for creating a new reinsurance treaty."""

    treaty_type: str = Field(..., description="quota_share, excess_of_loss, surplus, or facultative")
    reinsurer_name: str = Field(..., min_length=1, max_length=200)
    effective_date: str = Field(..., description="ISO-8601 date")
    expiration_date: str = Field(..., description="ISO-8601 date")
    lines_of_business: list[str] = Field(default_factory=list)
    retention: float = 0
    limit: float = 0
    rate: float = 0
    capacity_total: float = 0
    reinstatements: int = 0
    description: str = ""


class TreatyResponse(BaseModel):
    """Public representation of a reinsurance treaty."""

    id: str
    treaty_number: str
    treaty_type: str
    reinsurer_name: str
    status: str
    effective_date: str
    expiration_date: str
    lines_of_business: list[str]
    retention: float
    limit: float
    rate: float
    capacity_total: float
    capacity_used: float
    reinstatements: int
    description: str
    created_at: str
    updated_at: str


class TreatyList(BaseModel):
    """Paginated list of treaties."""

    items: list[TreatyResponse]
    total: int
    skip: int
    limit: int


class UtilizationResponse(BaseModel):
    """Capacity utilization for a treaty."""

    treaty_id: str
    treaty_number: str
    capacity_total: float
    capacity_used: float
    capacity_remaining: float
    utilization_pct: float
    cession_count: int


class CessionCreate(BaseModel):
    """Payload for recording a cession."""

    treaty_id: str
    policy_id: str
    policy_number: str
    ceded_premium: float = Field(..., gt=0)
    ceded_limit: float = Field(..., gt=0)
    cession_date: str | None = Field(None, description="ISO-8601 date")


class CessionResponse(BaseModel):
    """Public representation of a cession record."""

    id: str
    treaty_id: str
    policy_id: str
    policy_number: str
    ceded_premium: float
    ceded_limit: float
    cession_date: str | None
    created_at: str


class CessionList(BaseModel):
    """Paginated list of cessions."""

    items: list[CessionResponse]
    total: int
    skip: int
    limit: int


class RecoveryCreate(BaseModel):
    """Payload for recording a reinsurance recovery."""

    treaty_id: str
    claim_id: str
    claim_number: str
    recovery_amount: float = Field(..., gt=0)
    recovery_date: str | None = Field(None, description="ISO-8601 date")
    status: str = "pending"


class RecoveryResponse(BaseModel):
    """Public representation of a recovery record."""

    id: str
    treaty_id: str
    claim_id: str
    claim_number: str
    recovery_amount: float
    recovery_date: str | None
    status: str
    created_at: str


class RecoveryList(BaseModel):
    """Paginated list of recoveries."""

    items: list[RecoveryResponse]
    total: int
    skip: int
    limit: int


class BordereauResponse(BaseModel):
    """Bordereau report for a treaty."""

    treaty_id: str
    treaty_number: str
    reinsurer_name: str
    period_start: str | None
    period_end: str | None
    total_ceded_premium: float
    total_ceded_limit: float
    total_recoveries: float
    cession_count: int
    recovery_count: int
    cessions: list[dict[str, Any]]
    recoveries: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _generate_treaty_number() -> str:
    return f"TRE-{uuid.uuid4().hex[:8].upper()}"


async def _get_treaty(treaty_id: str) -> dict[str, Any]:
    treaty = await _treaty_repo.get_by_id(treaty_id)
    if treaty is None:
        raise HTTPException(status_code=404, detail=f"Treaty {treaty_id} not found")
    return treaty


# ---------------------------------------------------------------------------
# Treaty endpoints
# ---------------------------------------------------------------------------


@router.post("/treaties", response_model=TreatyResponse, status_code=201)
async def create_treaty(body: TreatyCreate) -> TreatyResponse:
    """Create a new reinsurance treaty."""
    tid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": tid,
        "treaty_number": _generate_treaty_number(),
        "treaty_type": body.treaty_type,
        "reinsurer_name": body.reinsurer_name,
        "status": "active",
        "effective_date": body.effective_date,
        "expiration_date": body.expiration_date,
        "lines_of_business": body.lines_of_business,
        "retention": body.retention,
        "limit": body.limit,
        "rate": body.rate,
        "capacity_total": body.capacity_total,
        "capacity_used": 0,
        "reinstatements": body.reinstatements,
        "description": body.description,
        "created_at": now,
        "updated_at": now,
    }
    await _treaty_repo.create(record)
    return TreatyResponse(**record)


@router.get("/treaties", response_model=TreatyList)
async def list_treaties(
    status: str | None = Query(None, description="Filter by treaty status"),
    treaty_type: str | None = Query(None, description="Filter by treaty type"),
    reinsurer: str | None = Query(None, description="Filter by reinsurer name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TreatyList:
    """List reinsurance treaties with optional filtering."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if treaty_type is not None:
        filters["treaty_type"] = treaty_type
    if reinsurer is not None:
        filters["reinsurer_name"] = reinsurer

    try:
        total = await _treaty_repo.count(filters)
        page = await _treaty_repo.list_all(filters=filters, skip=skip, limit=limit)
    except Exception:
        logger.warning("reinsurance.treaties_unavailable", exc_info=True)
        return TreatyList(items=[], total=0, skip=skip, limit=limit)
    return TreatyList(
        items=[TreatyResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/treaties/{treaty_id}", response_model=TreatyResponse)
async def get_treaty(treaty_id: str) -> TreatyResponse:
    """Retrieve a single treaty by ID."""
    return TreatyResponse(**await _get_treaty(treaty_id))


@router.get("/treaties/{treaty_id}/utilization", response_model=UtilizationResponse)
async def get_treaty_utilization(treaty_id: str) -> UtilizationResponse:
    """Get capacity utilization for a treaty."""
    treaty = await _get_treaty(treaty_id)

    # Count cessions for this treaty
    treaty_cessions = await _cession_repo.list_all(filters={"treaty_id": treaty_id})

    capacity_total = treaty.get("capacity_total", 0)
    capacity_used = treaty.get("capacity_used", 0)
    capacity_remaining = max(0, capacity_total - capacity_used)
    utilization_pct = (capacity_used / capacity_total * 100) if capacity_total > 0 else 0

    return UtilizationResponse(
        treaty_id=treaty_id,
        treaty_number=treaty["treaty_number"],
        capacity_total=capacity_total,
        capacity_used=capacity_used,
        capacity_remaining=capacity_remaining,
        utilization_pct=round(utilization_pct, 2),
        cession_count=len(treaty_cessions),
    )


# ---------------------------------------------------------------------------
# Cession endpoints
# ---------------------------------------------------------------------------


@router.post("/cessions", response_model=CessionResponse, status_code=201)
async def create_cession(body: CessionCreate) -> CessionResponse:
    """Record a cession of a policy to a treaty."""
    # Verify treaty exists
    treaty = await _get_treaty(body.treaty_id)

    cid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": cid,
        "treaty_id": body.treaty_id,
        "policy_id": body.policy_id,
        "policy_number": body.policy_number,
        "ceded_premium": body.ceded_premium,
        "ceded_limit": body.ceded_limit,
        "cession_date": body.cession_date or date.today().isoformat(),
        "created_at": now,
    }
    await _cession_repo.create(record)

    # Update treaty capacity used
    treaty["capacity_used"] = treaty.get("capacity_used", 0) + body.ceded_limit
    treaty["updated_at"] = now

    return CessionResponse(**record)


@router.get("/cessions", response_model=CessionList)
async def list_cessions(
    treaty_id: str | None = Query(None, description="Filter by treaty ID"),
    policy_id: str | None = Query(None, description="Filter by policy ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> CessionList:
    """List cessions with optional filtering by treaty or policy."""
    filters: dict[str, Any] = {}
    if treaty_id is not None:
        filters["treaty_id"] = treaty_id
    if policy_id is not None:
        filters["policy_id"] = policy_id

    try:
        total = await _cession_repo.count(filters or None)
        results = await _cession_repo.list_all(filters=filters or None, skip=skip, limit=limit)
    except Exception:
        logger.warning("reinsurance.cessions_unavailable", exc_info=True)
        return CessionList(items=[], total=0, skip=skip, limit=limit)
    return CessionList(
        items=[CessionResponse(**c) for c in results],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Recovery endpoints
# ---------------------------------------------------------------------------


@router.post("/recoveries", response_model=RecoveryResponse, status_code=201)
async def create_recovery(body: RecoveryCreate) -> RecoveryResponse:
    """Record a reinsurance recovery on a claim."""
    # Verify treaty exists
    await _get_treaty(body.treaty_id)

    rid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": rid,
        "treaty_id": body.treaty_id,
        "claim_id": body.claim_id,
        "claim_number": body.claim_number,
        "recovery_amount": body.recovery_amount,
        "recovery_date": body.recovery_date or date.today().isoformat(),
        "status": body.status,
        "created_at": now,
    }
    await _recovery_repo.create(record)
    return RecoveryResponse(**record)


@router.get("/recoveries", response_model=RecoveryList)
async def list_recoveries(
    treaty_id: str | None = Query(None, description="Filter by treaty ID"),
    claim_id: str | None = Query(None, description="Filter by claim ID"),
    status: str | None = Query(None, description="Filter by recovery status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> RecoveryList:
    """List recoveries with optional filtering."""
    filters: dict[str, Any] = {}
    if treaty_id is not None:
        filters["treaty_id"] = treaty_id
    if claim_id is not None:
        filters["claim_id"] = claim_id
    if status is not None:
        filters["status"] = status

    try:
        total = await _recovery_repo.count(filters or None)
        results = await _recovery_repo.list_all(filters=filters or None, skip=skip, limit=limit)
    except Exception:
        logger.warning("reinsurance.recoveries_unavailable", exc_info=True)
        return RecoveryList(items=[], total=0, skip=skip, limit=limit)
    return RecoveryList(
        items=[RecoveryResponse(**r) for r in results],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Bordereau endpoint
# ---------------------------------------------------------------------------


@router.get("/bordereaux/{treaty_id}", response_model=BordereauResponse)
async def get_bordereau(
    treaty_id: str,
    period_start: str | None = Query(None, description="Period start date (ISO-8601)"),
    period_end: str | None = Query(None, description="Period end date (ISO-8601)"),
) -> BordereauResponse:
    """Generate bordereau report for a treaty."""
    treaty = await _get_treaty(treaty_id)

    # Collect cessions and recoveries for this treaty via repositories
    treaty_cessions = await _cession_repo.list_all(filters={"treaty_id": treaty_id}, skip=0, limit=10000)
    treaty_recoveries = await _recovery_repo.list_all(filters={"treaty_id": treaty_id}, skip=0, limit=10000)

    # Apply period filter if provided
    if period_start:
        treaty_cessions = [c for c in treaty_cessions if c.get("cession_date") and c["cession_date"] >= period_start]
        treaty_recoveries = [
            r for r in treaty_recoveries if r.get("recovery_date") and r["recovery_date"] >= period_start
        ]
    if period_end:
        treaty_cessions = [c for c in treaty_cessions if c.get("cession_date") and c["cession_date"] <= period_end]
        treaty_recoveries = [
            r for r in treaty_recoveries if r.get("recovery_date") and r["recovery_date"] <= period_end
        ]

    total_ceded_premium = sum(c.get("ceded_premium", 0) for c in treaty_cessions)
    total_ceded_limit = sum(c.get("ceded_limit", 0) for c in treaty_cessions)
    total_recoveries = sum(r.get("recovery_amount", 0) for r in treaty_recoveries)

    return BordereauResponse(
        treaty_id=treaty_id,
        treaty_number=treaty["treaty_number"],
        reinsurer_name=treaty["reinsurer_name"],
        period_start=period_start,
        period_end=period_end,
        total_ceded_premium=total_ceded_premium,
        total_ceded_limit=total_ceded_limit,
        total_recoveries=total_recoveries,
        cession_count=len(treaty_cessions),
        recovery_count=len(treaty_recoveries),
        cessions=treaty_cessions,
        recoveries=treaty_recoveries,
    )
