"""MGA Oversight API — carrier-only endpoints for managing delegated authorities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_authorities: dict[str, dict[str, Any]] = {}
_bordereaux: dict[str, dict[str, Any]] = {}

# Seed sample MGA data
_SEED_MGAS: list[dict[str, Any]] = [
    {
        "mga_id": "mga-001",
        "mga_name": "Pacific Specialty MGA",
        "status": "active",
        "effective_date": "2024-01-01",
        "expiration_date": "2026-12-31",
        "lines_of_business": ["cyber", "professional_liability"],
        "premium_authority": 5_000_000,
        "premium_written": 3_200_000,
        "claims_authority": 500_000,
        "loss_ratio": 0.42,
        "compliance_score": 94,
        "last_audit_date": "2025-09-15",
    },
    {
        "mga_id": "mga-002",
        "mga_name": "Coastal Risk Partners",
        "status": "active",
        "effective_date": "2024-06-01",
        "expiration_date": "2026-05-31",
        "lines_of_business": ["general_liability", "epli"],
        "premium_authority": 8_000_000,
        "premium_written": 6_500_000,
        "claims_authority": 750_000,
        "loss_ratio": 0.58,
        "compliance_score": 87,
        "last_audit_date": "2025-07-20",
    },
    {
        "mga_id": "mga-003",
        "mga_name": "Summit Delegated Authority",
        "status": "suspended",
        "effective_date": "2023-03-01",
        "expiration_date": "2025-02-28",
        "lines_of_business": ["dnol"],
        "premium_authority": 3_000_000,
        "premium_written": 2_900_000,
        "claims_authority": 300_000,
        "loss_ratio": 0.71,
        "compliance_score": 62,
        "last_audit_date": "2025-04-10",
    },
]

_SEED_BORDEREAUX: list[dict[str, Any]] = [
    {
        "id": "bx-001",
        "mga_id": "mga-001",
        "period": "2026-Q1",
        "premium_reported": 820_000,
        "claims_reported": 340_000,
        "loss_ratio": 0.41,
        "policy_count": 145,
        "claim_count": 12,
        "status": "validated",
        "exceptions": [],
    },
    {
        "id": "bx-002",
        "mga_id": "mga-002",
        "period": "2026-Q1",
        "premium_reported": 1_650_000,
        "claims_reported": 980_000,
        "loss_ratio": 0.59,
        "policy_count": 312,
        "claim_count": 28,
        "status": "exceptions",
        "exceptions": ["3 policies missing coverage verification", "Late submission"],
    },
    {
        "id": "bx-003",
        "mga_id": "mga-003",
        "period": "2025-Q4",
        "premium_reported": 710_000,
        "claims_reported": 520_000,
        "loss_ratio": 0.73,
        "policy_count": 98,
        "claim_count": 19,
        "status": "pending",
        "exceptions": ["Authority suspended — review required"],
    },
]


def _seed() -> None:
    if not _authorities:
        for m in _SEED_MGAS:
            _authorities[m["mga_id"]] = {**m, "id": m["mga_id"]}
    if not _bordereaux:
        for b in _SEED_BORDEREAUX:
            _bordereaux[b["id"]] = b


_seed()


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AuthorityResponse(BaseModel):
    mga_id: str
    mga_name: str
    status: str
    effective_date: str | None = None
    expiration_date: str | None = None
    lines_of_business: list[str] = Field(default_factory=list)
    premium_authority: float = 0
    premium_written: float = 0
    claims_authority: float = 0
    loss_ratio: float = 0
    compliance_score: float = 100
    last_audit_date: str | None = None


class BordereauSubmit(BaseModel):
    mga_id: str
    period: str
    premium_reported: float = 0
    claims_reported: float = 0
    policy_count: int = 0
    claim_count: int = 0


class BordereauResponse(BaseModel):
    id: str
    mga_id: str
    period: str
    premium_reported: float = 0
    claims_reported: float = 0
    loss_ratio: float = 0
    policy_count: int = 0
    claim_count: int = 0
    status: str = "pending"
    exceptions: list[str] = Field(default_factory=list)


class PerformanceSummary(BaseModel):
    total_mgas: int
    active_mgas: int
    suspended_mgas: int
    total_premium_written: float
    total_premium_authority: float
    average_loss_ratio: float
    average_compliance_score: float
    authorities: list[AuthorityResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/authorities", response_model=list[AuthorityResponse])
async def list_authorities(
    status: str | None = Query(None, description="Filter by status"),
) -> list[AuthorityResponse]:
    """List all MGA authorities."""
    _seed()
    items = list(_authorities.values())
    if status:
        items = [a for a in items if a.get("status") == status]
    return [AuthorityResponse(**a) for a in items]


@router.get("/authorities/{mga_id}", response_model=AuthorityResponse)
async def get_authority(mga_id: str) -> AuthorityResponse:
    """Get MGA detail + performance."""
    _seed()
    auth = _authorities.get(mga_id)
    if not auth:
        raise HTTPException(status_code=404, detail=f"MGA {mga_id} not found")
    return AuthorityResponse(**auth)


@router.post("/bordereaux", response_model=BordereauResponse, status_code=201)
async def submit_bordereau(body: BordereauSubmit) -> BordereauResponse:
    """Submit a bordereau for an MGA."""
    _seed()
    if body.mga_id not in _authorities:
        raise HTTPException(status_code=404, detail=f"MGA {body.mga_id} not found")

    bid = f"bx-{uuid.uuid4().hex[:8]}"
    loss_ratio = round(body.claims_reported / body.premium_reported, 4) if body.premium_reported > 0 else 0
    record: dict[str, Any] = {
        "id": bid,
        "mga_id": body.mga_id,
        "period": body.period,
        "premium_reported": body.premium_reported,
        "claims_reported": body.claims_reported,
        "loss_ratio": loss_ratio,
        "policy_count": body.policy_count,
        "claim_count": body.claim_count,
        "status": "pending",
        "exceptions": [],
    }
    _bordereaux[bid] = record
    return BordereauResponse(**record)


@router.get("/bordereaux", response_model=list[BordereauResponse])
async def list_bordereaux(
    mga_id: str | None = Query(None, description="Filter by MGA"),
) -> list[BordereauResponse]:
    """List bordereaux."""
    _seed()
    items = list(_bordereaux.values())
    if mga_id:
        items = [b for b in items if b.get("mga_id") == mga_id]
    return [BordereauResponse(**b) for b in items]


@router.get("/performance", response_model=PerformanceSummary)
async def mga_performance() -> PerformanceSummary:
    """MGA performance summary across all authorities."""
    _seed()
    auths = list(_authorities.values())
    active = [a for a in auths if a.get("status") == "active"]
    suspended = [a for a in auths if a.get("status") == "suspended"]
    total_written = sum(a.get("premium_written", 0) for a in auths)
    total_authority = sum(a.get("premium_authority", 0) for a in auths)
    avg_lr = sum(a.get("loss_ratio", 0) for a in auths) / len(auths) if auths else 0
    avg_cs = sum(a.get("compliance_score", 0) for a in auths) / len(auths) if auths else 0
    return PerformanceSummary(
        total_mgas=len(auths),
        active_mgas=len(active),
        suspended_mgas=len(suspended),
        total_premium_written=total_written,
        total_premium_authority=total_authority,
        average_loss_ratio=round(avg_lr, 4),
        average_compliance_score=round(avg_cs, 2),
        authorities=[AuthorityResponse(**a) for a in auths],
    )
