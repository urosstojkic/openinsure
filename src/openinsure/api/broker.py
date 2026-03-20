"""Broker portal API — filtered views for external broker partners.

Exposes submissions, policies, and claims with internal-only fields
stripped to maintain data separation between carrier and broker views.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

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


@router.get("/submissions")
async def broker_submissions(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    """Broker's own submissions — internal scoring data stripped."""
    repo = get_submission_repository()
    subs = await repo.list_all(limit=limit)
    return {
        "items": [_sanitize_for_broker(s) for s in subs],
        "total": len(subs),
    }


@router.get("/policies")
async def broker_policies(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    """Policies visible to broker — endorsement details excluded."""
    repo = get_policy_repository()
    pols = await repo.list_all(limit=limit)
    return {
        "items": [_sanitize_policy(p) for p in pols],
        "total": len(pols),
    }


@router.get("/claims")
async def broker_claims(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    """Claims visible to broker — fraud and reserve details excluded."""
    repo = get_claim_repository()
    claims = await repo.list_all(limit=limit)
    return {
        "items": [_sanitize_claim(c) for c in claims],
        "total": len(claims),
    }


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
