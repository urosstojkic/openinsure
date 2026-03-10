"""Renewal workflow API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_policy_repository
from openinsure.services.renewal import generate_renewal_terms, identify_renewals

router = APIRouter()

_repo = get_policy_repository()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RenewalCandidate(BaseModel):
    id: str
    policy_number: str = ""
    policyholder_name: str = ""
    status: str = ""
    effective_date: str = ""
    expiration_date: str = ""
    premium: float = 0
    days_to_expiry: int = 0


class RenewalTerms(BaseModel):
    original_policy: str | None = None
    renewal_premium: float = 0
    effective_date: str | None = None
    changes: list[str] = Field(default_factory=list)
    recommendation: str = "review_required"


class RenewalResult(BaseModel):
    policy_id: str
    renewal_policy_id: str | None = None
    status: str
    terms: RenewalTerms | None = None
    message: str = ""


class UpcomingRenewals(BaseModel):
    total: int
    within_30_days: int
    within_60_days: int
    within_90_days: int
    renewals: list[RenewalCandidate]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/upcoming", response_model=UpcomingRenewals)
async def list_upcoming_renewals(
    days: int = Query(90, ge=1, le=365, description="Look-ahead window in days"),
) -> UpcomingRenewals:
    """List policies approaching renewal."""
    candidates = await identify_renewals(days_ahead=days)

    within_30 = [c for c in candidates if c.get("days_to_expiry", 999) <= 30]
    within_60 = [c for c in candidates if c.get("days_to_expiry", 999) <= 60]
    within_90 = [c for c in candidates if c.get("days_to_expiry", 999) <= 90]

    items = [
        RenewalCandidate(
            id=c.get("id", ""),
            policy_number=c.get("policy_number", ""),
            policyholder_name=c.get("policyholder_name", ""),
            status=c.get("status", ""),
            effective_date=str(c.get("effective_date", "")),
            expiration_date=str(c.get("expiration_date", "")),
            premium=float(c.get("premium", 0) or 0),
            days_to_expiry=c.get("days_to_expiry", 0),
        )
        for c in candidates
    ]

    return UpcomingRenewals(
        total=len(items),
        within_30_days=len(within_30),
        within_60_days=len(within_60),
        within_90_days=len(within_90),
        renewals=items,
    )


@router.post("/{policy_id}/generate", response_model=RenewalTerms)
async def generate_terms(policy_id: str) -> RenewalTerms:
    """Generate renewal terms for a policy."""
    policy = await _repo.get_by_id(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    terms = await generate_renewal_terms(policy)
    return RenewalTerms(**terms)


@router.post("/{policy_id}/process", response_model=RenewalResult)
async def process_renewal(policy_id: str) -> RenewalResult:
    """Process renewal — generate terms and create the renewal policy."""
    policy = await _repo.get_by_id(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    terms = await generate_renewal_terms(policy)

    new_pid = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    new_effective = policy.get("expiration_date", "")
    # Add 1 year
    new_expiration = (
        str(new_effective).replace(str(new_effective)[:4], str(int(str(new_effective)[:4]) + 1), 1)
        if new_effective
        else ""
    )

    renewal_record: dict[str, Any] = {
        **policy,
        "id": new_pid,
        "policy_number": f"POL-{uuid.uuid4().hex[:8].upper()}",
        "status": "active",
        "effective_date": new_effective,
        "expiration_date": new_expiration,
        "premium": terms["renewal_premium"],
        "endorsements": [],
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(renewal_record)

    return RenewalResult(
        policy_id=policy_id,
        renewal_policy_id=new_pid,
        status="renewed",
        terms=RenewalTerms(**terms),
        message="Renewal processed successfully",
    )
