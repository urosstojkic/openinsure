"""Actuarial API — carrier-only endpoints for reserves, triangles & rate adequacy.

Uses factory-provided repositories that route to in-memory or SQL backends
depending on configuration.  Backed by the actuarial service layer for
chain-ladder IBNR estimation and rate-adequacy calculations.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from openinsure.infrastructure.factory import (
    get_actuarial_reserve_repository,
    get_rate_adequacy_repository,
    get_triangle_repository,
)
from openinsure.services.actuarial import (
    Triangle,
    estimate_ibnr,
    generate_loss_triangle,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Repositories — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_reserve_repo = get_actuarial_reserve_repository()
_triangle_repo = get_triangle_repository()
_rate_adequacy_repo = get_rate_adequacy_repository()


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ReserveCreate(BaseModel):
    line_of_business: str
    accident_year: int
    reserve_type: str
    carried_amount: float = 0
    indicated_amount: float = 0
    selected_amount: float = 0
    as_of_date: str | None = None
    analyst: str = ""
    approved_by: str = ""
    notes: str = ""


class ReserveResponse(BaseModel):
    id: str
    line_of_business: str
    accident_year: int
    reserve_type: str
    carried_amount: float = 0
    indicated_amount: float = 0
    selected_amount: float = 0
    as_of_date: str | None = None
    analyst: str = ""
    approved_by: str = ""
    notes: str = ""


class TriangleEntryResponse(BaseModel):
    accident_year: int
    development_month: int
    incurred_amount: float = 0
    paid_amount: float = 0
    case_reserve: float = 0
    claim_count: int = 0


class TriangleResponse(BaseModel):
    line_of_business: str
    entries: list[TriangleEntryResponse]
    accident_years: list[int]
    development_months: list[int]


class IBNRResponse(BaseModel):
    line_of_business: str
    method: str
    factors: dict[str, str]
    ultimates: dict[str, str]
    ibnr_by_year: dict[str, str]
    total_ibnr: str


class RateAdequacyItem(BaseModel):
    line_of_business: str
    segment: str
    current_rate: str
    indicated_rate: str
    adequacy_ratio: str


class RateAdequacyResponse(BaseModel):
    items: list[RateAdequacyItem]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/reserves", response_model=list[ReserveResponse])
async def list_reserves(
    lob: str | None = Query(None, description="Filter by line of business"),
    accident_year: int | None = Query(None, description="Filter by accident year"),
) -> list[ReserveResponse]:
    """List actuarial reserves, optionally filtered by LOB and accident year."""
    filters: dict[str, Any] = {}
    if lob:
        filters["line_of_business"] = lob
    if accident_year:
        filters["accident_year"] = accident_year
    items = await _reserve_repo.list_all(filters=filters or None, skip=0, limit=200)
    return [ReserveResponse(**r) for r in items]


@router.post("/reserves", response_model=ReserveResponse, status_code=201)
async def set_reserve(body: ReserveCreate) -> ReserveResponse:
    """Create or update an actuarial reserve."""
    rid = f"res-{uuid.uuid4().hex[:8]}"
    record: dict[str, Any] = {
        "id": rid,
        "line_of_business": body.line_of_business,
        "accident_year": body.accident_year,
        "reserve_type": body.reserve_type,
        "carried_amount": body.carried_amount,
        "indicated_amount": body.indicated_amount,
        "selected_amount": body.selected_amount,
        "as_of_date": body.as_of_date,
        "analyst": body.analyst,
        "approved_by": body.approved_by,
        "notes": body.notes,
    }
    await _reserve_repo.create(record)
    return ReserveResponse(**record)


@router.get("/triangles/{lob}", response_model=TriangleResponse)
async def get_loss_triangle(lob: str) -> TriangleResponse:
    """Get the loss-development triangle for a line of business."""
    entries = await _triangle_repo.list_all(filters={"line_of_business": lob}, skip=0, limit=500)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No triangle data for LOB '{lob}'",
        )
    accident_years = sorted({e["accident_year"] for e in entries})
    dev_months = sorted({e["development_month"] for e in entries})
    return TriangleResponse(
        line_of_business=lob,
        entries=[TriangleEntryResponse(**e) for e in entries],
        accident_years=accident_years,
        development_months=dev_months,
    )


@router.post("/triangles/{lob}/generate", response_model=TriangleResponse)
async def generate_triangle(lob: str) -> TriangleResponse:
    """Generate a loss triangle from stored claims data for the LOB.

    In the seed implementation this re-processes the existing triangle entries.
    In production it would pull from the claims data store.
    """
    entries = await _triangle_repo.list_all(filters={"line_of_business": lob}, skip=0, limit=500)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No claims data available for LOB '{lob}'",
        )

    # Re-generate via service layer (validates round-trip)
    triangle_dict = generate_loss_triangle(lob, entries)

    # Flatten back to entry list for response
    generated: list[dict[str, Any]] = []
    for ay, row in triangle_dict.items():
        for dm, amt in row.items():
            # Pull matching seed row for paid/case/count if available
            match = next(
                (e for e in entries if e["accident_year"] == ay and e["development_month"] == dm),
                {},
            )
            generated.append(
                {
                    "accident_year": ay,
                    "development_month": dm,
                    "incurred_amount": float(amt),
                    "paid_amount": match.get("paid_amount", 0),
                    "case_reserve": match.get("case_reserve", 0),
                    "claim_count": match.get("claim_count", 0),
                }
            )

    accident_years = sorted({e["accident_year"] for e in generated})
    dev_months = sorted({e["development_month"] for e in generated})
    return TriangleResponse(
        line_of_business=lob,
        entries=[TriangleEntryResponse(**e) for e in generated],
        accident_years=accident_years,
        development_months=dev_months,
    )


@router.get("/rate-adequacy", response_model=RateAdequacyResponse)
async def rate_adequacy(
    lob: str | None = Query(None, description="Filter by line of business"),
) -> RateAdequacyResponse:
    """Return rate-adequacy analysis by segment."""
    filters: dict[str, Any] = {}
    if lob:
        filters["line_of_business"] = lob
    items = await _rate_adequacy_repo.list_all(filters=filters or None, skip=0, limit=200)
    return RateAdequacyResponse(
        items=[RateAdequacyItem(**i) for i in items],
        total=len(items),
    )


@router.get("/ibnr/{lob}", response_model=IBNRResponse)
async def get_ibnr(
    lob: str,
    method: str = Query("chain_ladder", description="IBNR estimation method"),
) -> IBNRResponse:
    """Estimate IBNR reserves for a line of business using the specified method."""
    entries = await _triangle_repo.list_all(filters={"line_of_business": lob}, skip=0, limit=500)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No triangle data for LOB '{lob}'",
        )

    # Build the triangle dict the service expects
    triangle: Triangle = {}
    for e in entries:
        ay = e["accident_year"]
        dm = e["development_month"]
        amt = Decimal(str(e["incurred_amount"]))
        triangle.setdefault(ay, {})[dm] = amt

    result = estimate_ibnr(triangle, method=method)

    return IBNRResponse(
        line_of_business=lob,
        method=method,
        **result,
    )
