"""GDPR compliance API endpoints for OpenInsure.

Provides endpoints for GDPR rights:
- Art 7: Consent tracking
- Art 17: Right to erasure
- Art 20: Data portability
- Data retention policy management

Issue #165 — GDPR Compliance.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openinsure.services.gdpr_service import get_gdpr_service

router = APIRouter()
_logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ConsentGrantRequest(BaseModel):
    """Payload for granting consent."""

    purpose: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Consent purpose, e.g. 'insurance_underwriting', 'marketing'",
    )
    evidence: str = Field(
        default="",
        max_length=2000,
        description="How consent was obtained",
    )


class ConsentResponse(BaseModel):
    """Consent record response."""

    id: str = ""
    party_id: str = ""
    purpose: str = ""
    status: str = ""
    granted_at: str | None = None
    withdrawn_at: str | None = None
    expires_at: str | None = None
    evidence: str = ""
    created_at: str = ""


class ErasureResponse(BaseModel):
    """Result of an erasure request."""

    status: str
    party_id: str = ""
    detail: str | None = None
    fields_anonymised: list[str] = Field(default_factory=list)
    performed_at: str | None = None
    active_policy_count: int | None = None


class ExportResponse(BaseModel):
    """Data portability export result."""

    status: str
    party_id: str = ""
    detail: str | None = None
    exported_at: str | None = None
    personal_data: dict[str, Any] = Field(default_factory=dict)
    insurance_data: dict[str, Any] = Field(default_factory=dict)


class RetentionPolicyResponse(BaseModel):
    """Data retention policy."""

    id: str = ""
    entity_type: str = ""
    retention_years: int = 0
    legal_basis: str | None = None
    auto_anonymize: bool = True


class ConsentWithdrawResponse(BaseModel):
    """Result of a consent withdrawal."""

    party_id: str = ""
    purpose: str = ""
    status: str = ""
    withdrawn_count: int = 0
    withdrawn_at: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/erasure-request/{party_id}",
    response_model=ErasureResponse,
    summary="Art 17: Right to erasure",
)
async def process_erasure_request(party_id: str) -> ErasureResponse:
    """Process a GDPR erasure request for a party.

    Anonymises PII while preserving financial/insurance records
    required by regulation. Blocked if the party has active policies.
    """
    svc = get_gdpr_service()
    result = await svc.process_erasure_request(party_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("detail", "Not found"))
    return ErasureResponse(**result)


@router.get(
    "/export/{party_id}",
    response_model=ExportResponse,
    summary="Art 20: Data portability",
)
async def export_personal_data(party_id: str) -> ExportResponse:
    """Export all personal data for a party in machine-readable format.

    Includes party info, addresses, contacts, submissions, policies, and claims.
    """
    svc = get_gdpr_service()
    result = await svc.export_personal_data(party_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("detail", "Not found"))
    return ExportResponse(**result)


@router.get(
    "/consent/{party_id}",
    response_model=list[ConsentResponse],
    summary="Art 7: Get consent status",
)
async def get_consent_status(party_id: str) -> list[ConsentResponse]:
    """Get all consent records for a party."""
    svc = get_gdpr_service()
    records = await svc.get_consent_status(party_id)
    return [ConsentResponse(**r) for r in records]


@router.post(
    "/consent/{party_id}",
    response_model=ConsentResponse,
    status_code=201,
    summary="Grant consent",
)
async def grant_consent(
    party_id: str,
    body: ConsentGrantRequest,
) -> ConsentResponse:
    """Record a consent grant for a party."""
    svc = get_gdpr_service()
    record = await svc.grant_consent(
        party_id=party_id,
        purpose=body.purpose,
        evidence=body.evidence,
    )
    return ConsentResponse(**record)


@router.delete(
    "/consent/{party_id}/{purpose}",
    response_model=ConsentWithdrawResponse,
    summary="Withdraw consent",
)
async def withdraw_consent(party_id: str, purpose: str) -> ConsentWithdrawResponse:
    """Withdraw consent for a specific purpose."""
    svc = get_gdpr_service()
    result = await svc.withdraw_consent(party_id=party_id, purpose=purpose)
    return ConsentWithdrawResponse(**result)


@router.get(
    "/retention-policies",
    response_model=list[RetentionPolicyResponse],
    summary="List retention policies",
)
async def list_retention_policies() -> list[RetentionPolicyResponse]:
    """List all data retention policies."""
    svc = get_gdpr_service()
    policies = await svc.list_retention_policies()
    return [RetentionPolicyResponse(**p) for p in policies]
