"""Party API endpoints for OpenInsure.

Provides party search and customer 360° view.

Issue #157 — Customer/Applicant Deduplication.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.services.party_resolution import get_party_resolution_service

router = APIRouter()
_logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PartyResponse(BaseModel):
    """Party record."""

    id: str = ""
    name: str = ""
    party_type: str = "organization"
    roles: list[str] = Field(default_factory=list)
    tax_id: str | None = None
    registration_number: str | None = None
    addresses: list[dict[str, Any]] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class Customer360Response(BaseModel):
    """Consolidated customer view."""

    party: dict[str, Any] = Field(default_factory=dict)
    submissions: list[dict[str, Any]] = Field(default_factory=list)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class PartySearchResponse(BaseModel):
    """Party search results."""

    items: list[PartyResponse]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{party_id}/360",
    response_model=Customer360Response,
    summary="Customer 360° view",
)
async def get_customer_360(party_id: str) -> Customer360Response:
    """Get all submissions, policies, and claims for a customer."""
    svc = get_party_resolution_service()
    result = await svc.get_customer_360(party_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Party not found")
    return Customer360Response(**result)


@router.get(
    "/search",
    response_model=PartySearchResponse,
    summary="Search parties",
)
async def search_parties(
    name: str | None = Query(None, description="Search by name (case-insensitive prefix)"),
    tax_id: str | None = Query(None, description="Search by tax ID (exact match)"),
    limit: int = Query(20, ge=1, le=100),
) -> PartySearchResponse:
    """Search parties by name or tax ID."""
    svc = get_party_resolution_service()
    results = await svc.search_parties(name=name, tax_id=tax_id, limit=limit)
    items = [PartyResponse(**p) for p in results]
    return PartySearchResponse(items=items, total=len(items))


@router.get(
    "/{party_id}",
    response_model=PartyResponse,
    summary="Get party by ID",
)
async def get_party(party_id: str) -> PartyResponse:
    """Retrieve a party record by ID."""
    svc = get_party_resolution_service()
    party = await svc.get_party(party_id)
    if party is None:
        raise HTTPException(status_code=404, detail="Party not found")
    return PartyResponse(**party)
