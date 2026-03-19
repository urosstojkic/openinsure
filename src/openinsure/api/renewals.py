"""Renewal workflow API endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_policy_repository, get_renewal_repository
from openinsure.services.renewal import generate_renewal_terms, identify_renewals

router = APIRouter()

_repo = get_policy_repository()
_renewal_repo = get_renewal_repository()


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


class RenewalRecordResponse(BaseModel):
    id: str
    original_policy_id: str
    renewal_policy_id: str | None = None
    status: str = "pending"
    expiring_premium: float = 0
    renewal_premium: float = 0
    rate_change_pct: float = 0
    recommendation: str = "review_required"
    conditions: list[str] = Field(default_factory=list)
    generated_by: str = "system"
    created_at: str = ""
    updated_at: str = ""


class RenewalRecordList(BaseModel):
    items: list[RenewalRecordResponse]
    total: int


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


@router.post("/{policy_id}/generate")
async def generate_terms(policy_id: str) -> dict[str, object] | RenewalTerms:
    """Generate renewal terms for a policy."""
    from openinsure.agents.foundry_client import get_foundry_client

    policy = await _repo.get_by_id(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    foundry = get_foundry_client()
    if foundry.is_available:
        result = await foundry.invoke(
            "openinsure-underwriting",
            "Generate renewal terms for this expiring cyber policy.\n"
            "Consider: claims history, market conditions, expiring premium.\n"
            "Respond with JSON:\n"
            '{"renewal_premium": 15000, "rate_change_pct": 5.0, "confidence": 0.85, '
            '"conditions": ["annual pen test required"], "recommendation": "renew_as_is"}\n\n'
            f"Expiring policy: {json.dumps(policy, default=str)[:600]}",
        )
        resp = result.get("response", {})
        if isinstance(resp, dict) and result.get("source") == "foundry":
            from openinsure.services.event_publisher import publish_domain_event

            await publish_domain_event(
                "renewal.terms_generated",
                f"/policies/{policy_id}",
                {"policy_id": policy_id, "source": "foundry"},
            )
            return {
                "policy_id": policy_id,
                "original_policy": policy.get("policy_number"),
                "expiring_premium": policy.get("total_premium", policy.get("premium", 0)),
                "renewal_premium": resp.get("renewal_premium"),
                "rate_change_pct": resp.get("rate_change_pct"),
                "conditions": resp.get("conditions", []),
                "recommendation": resp.get("recommendation", "review_required"),
                "confidence": resp.get("confidence", 0.8),
                "source": "foundry",
            }

    # Existing local fallback
    terms = await generate_renewal_terms(policy)
    return RenewalTerms(**terms)


@router.post("/{policy_id}/process")
async def process_renewal(policy_id: str) -> dict[str, object]:
    """Process renewal — generate terms and create the renewal policy."""
    from openinsure.agents.foundry_client import get_foundry_client
    from openinsure.services.event_publisher import publish_domain_event

    policy = await _repo.get_by_id(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    foundry = get_foundry_client()
    results: dict[str, Any] = {}

    # Step 1: AI renewal assessment
    if foundry.is_available:
        uw = await foundry.invoke(
            "openinsure-underwriting",
            "Assess this renewal. Price the renewal policy.\n"
            'Respond with JSON: {"renewal_premium": X, "recommendation": "renew"/"non_renew", "confidence": 0.85}\n\n'
            f"Policy: {json.dumps(policy, default=str)[:600]}",
        )
        results["underwriting"] = uw

    # Step 2: Create renewal policy (if recommended)
    uw_resp = results.get("underwriting", {}).get("response", {})
    recommendation = "renew"
    renewal_premium = float(policy.get("total_premium", policy.get("premium", 10000))) * 1.05
    if isinstance(uw_resp, dict) and uw_resp:
        recommendation = uw_resp.get("recommendation", "renew")
        renewal_premium = float(uw_resp.get("renewal_premium", renewal_premium))

    new_policy_id = None
    if recommendation != "non_renew":
        new_policy_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        new_effective = str(policy.get("expiration_date", ""))
        new_expiration = (
            new_effective.replace(new_effective[:4], str(int(new_effective[:4]) + 1), 1) if new_effective else ""
        )
        new_policy: dict[str, Any] = {
            "id": new_policy_id,
            "policy_number": f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}",
            "policyholder_name": policy.get("policyholder_name", policy.get("insured_name", "")),
            "status": "active",
            "product_id": policy.get("product_id", "cyber-smb"),
            "submission_id": "",
            "effective_date": new_effective,
            "expiration_date": new_expiration,
            "premium": renewal_premium,
            "total_premium": renewal_premium,
            "written_premium": renewal_premium,
            "coverages": policy.get("coverages", []),
            "endorsements": [],
            "metadata": {"renewal_of": policy_id, "source": "renewal_workflow"},
            "documents": [],
            "created_at": now,
            "updated_at": now,
        }
        await _repo.create(new_policy)
        await publish_domain_event(
            "policy.renewed",
            f"/policies/{new_policy_id}",
            {"new_policy_id": new_policy_id, "original_policy_id": policy_id, "premium": renewal_premium},
        )

    # Step 3: Compliance
    if foundry.is_available:
        comp = await foundry.invoke(
            "openinsure-compliance",
            f"Audit this renewal workflow.\nOriginal: {json.dumps(policy, default=str)[:200]}\n"
            f"Renewal premium: {renewal_premium}\nRecommendation: {recommendation}",
        )
        results["compliance"] = comp

    result: dict[str, Any] = {
        "policy_id": policy_id,
        "workflow": "renewal",
        "outcome": recommendation,
        "new_policy_id": new_policy_id,
        "renewal_premium": renewal_premium,
        "steps": results,
    }

    # Persist the renewal record
    expiring_premium = float(policy.get("total_premium", policy.get("premium", 0)) or 0)
    rate_pct = ((renewal_premium - expiring_premium) / expiring_premium * 100) if expiring_premium else 0
    now = datetime.now(UTC).isoformat()
    renewal_record: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "original_policy_id": policy_id,
        "renewal_policy_id": new_policy_id,
        "status": "accepted" if new_policy_id else "non_renewed",
        "expiring_premium": expiring_premium,
        "renewal_premium": renewal_premium,
        "rate_change_pct": round(rate_pct, 2),
        "recommendation": recommendation,
        "conditions": [],
        "generated_by": "foundry" if foundry.is_available else "system",
        "created_at": now,
        "updated_at": now,
    }
    await _renewal_repo.create(renewal_record)

    return json.loads(json.dumps(result, default=str))


@router.get("/records", response_model=RenewalRecordList)
async def list_renewal_records(
    status: str | None = Query(None, description="Filter by renewal status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> RenewalRecordList:
    """List all renewal records."""
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    total = await _renewal_repo.count(filters or None)
    items = await _renewal_repo.list_all(filters=filters or None, skip=skip, limit=limit)
    return RenewalRecordList(
        items=[RenewalRecordResponse(**r) for r in items],
        total=total,
    )
