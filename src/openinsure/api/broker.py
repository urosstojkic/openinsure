"""Broker portal API — filtered views for external broker partners.

Exposes submissions, policies, and claims with internal-only fields
stripped to maintain data separation between carrier and broker views.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from openinsure.infrastructure.factory import (
    get_claim_repository,
    get_policy_repository,
    get_submission_repository,
)

router = APIRouter()

# Fields that must never be exposed to broker partners
_SUBMISSION_INTERNAL_FIELDS = frozenset(
    {"risk_score", "confidence", "triage_result", "decision_history", "assigned_to"}
)
_POLICY_INTERNAL_FIELDS = frozenset({"metadata", "endorsements"})
_CLAIM_INTERNAL_FIELDS = frozenset({"fraud_score", "reserves", "payments"})


class BrokerListResponse(BaseModel):
    """Standard paginated envelope for broker list endpoints."""

    items: list[dict[str, Any]]
    total: int
    skip: int
    limit: int


@router.get("/submissions", response_model=BrokerListResponse)
async def broker_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> BrokerListResponse:
    """Broker's own submissions — internal scoring data stripped."""
    repo = get_submission_repository()
    subs = await repo.list_all(limit=5000)
    sanitized = [_sanitize_for_broker(s) for s in subs]
    page = sanitized[skip : skip + limit]
    return BrokerListResponse(items=page, total=len(sanitized), skip=skip, limit=limit)


@router.get("/policies", response_model=BrokerListResponse)
async def broker_policies(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> BrokerListResponse:
    """Policies visible to broker — endorsement details excluded."""
    repo = get_policy_repository()
    pols = await repo.list_all(limit=5000)
    sanitized = [_sanitize_policy(p) for p in pols]
    page = sanitized[skip : skip + limit]
    return BrokerListResponse(items=page, total=len(sanitized), skip=skip, limit=limit)


@router.get("/claims", response_model=BrokerListResponse)
async def broker_claims(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> BrokerListResponse:
    """Claims visible to broker — fraud and reserve details excluded."""
    repo = get_claim_repository()
    claims = await repo.list_all(limit=5000)
    sanitized = [_sanitize_claim(c) for c in claims]
    page = sanitized[skip : skip + limit]
    return BrokerListResponse(items=page, total=len(sanitized), skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# Sanitisation helpers
# ---------------------------------------------------------------------------


def _sanitize_for_broker(sub: dict[str, Any]) -> dict[str, Any]:
    """Remove internal fields that brokers shouldn't see."""
    return {k: v for k, v in sub.items() if k not in _SUBMISSION_INTERNAL_FIELDS}


def _sanitize_policy(pol: dict[str, Any]) -> dict[str, Any]:
    """Remove internal policy fields."""
    return {k: v for k, v in pol.items() if k not in _POLICY_INTERNAL_FIELDS}


def _sanitize_claim(claim: dict[str, Any]) -> dict[str, Any]:
    """Remove internal claim fields."""
    return {k: v for k, v in claim.items() if k not in _CLAIM_INTERNAL_FIELDS}
