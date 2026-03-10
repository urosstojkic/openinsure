"""Actuarial API — carrier-only endpoints for reserves, triangles & rate adequacy.

Uses in-memory storage with seed data.  Backed by the actuarial service layer
for chain-ladder IBNR estimation and rate-adequacy calculations.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.services.actuarial import (
    Triangle,
    calculate_rate_adequacy,
    estimate_ibnr,
    generate_loss_triangle,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_reserves: dict[str, dict[str, Any]] = {}
_triangles: dict[str, list[dict[str, Any]]] = {}  # lob -> entries


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SEED_RESERVES: list[dict[str, Any]] = [
    {
        "id": "res-001",
        "line_of_business": "cyber",
        "accident_year": 2023,
        "reserve_type": "case",
        "carried_amount": 4_500_000,
        "indicated_amount": 4_800_000,
        "selected_amount": 4_650_000,
        "as_of_date": "2026-03-31",
        "analyst": "Sarah Chen",
        "approved_by": "Michael Torres",
        "notes": "Q1 2026 review — slight deterioration in large-loss corridor.",
    },
    {
        "id": "res-002",
        "line_of_business": "cyber",
        "accident_year": 2023,
        "reserve_type": "ibnr",
        "carried_amount": 2_100_000,
        "indicated_amount": 2_350_000,
        "selected_amount": 2_200_000,
        "as_of_date": "2026-03-31",
        "analyst": "Sarah Chen",
        "approved_by": "Michael Torres",
        "notes": "Chain-ladder indication; BF cross-check within 5%.",
    },
    {
        "id": "res-003",
        "line_of_business": "cyber",
        "accident_year": 2024,
        "reserve_type": "case",
        "carried_amount": 3_200_000,
        "indicated_amount": 3_400_000,
        "selected_amount": 3_300_000,
        "as_of_date": "2026-03-31",
        "analyst": "Sarah Chen",
        "approved_by": "",
        "notes": "Pending CFO approval.",
    },
    {
        "id": "res-004",
        "line_of_business": "cyber",
        "accident_year": 2024,
        "reserve_type": "ibnr",
        "carried_amount": 1_800_000,
        "indicated_amount": 2_000_000,
        "selected_amount": 1_900_000,
        "as_of_date": "2026-03-31",
        "analyst": "Sarah Chen",
        "approved_by": "",
        "notes": "",
    },
    {
        "id": "res-005",
        "line_of_business": "professional_liability",
        "accident_year": 2023,
        "reserve_type": "case",
        "carried_amount": 6_000_000,
        "indicated_amount": 6_200_000,
        "selected_amount": 6_100_000,
        "as_of_date": "2026-03-31",
        "analyst": "James Wright",
        "approved_by": "Michael Torres",
        "notes": "",
    },
    {
        "id": "res-006",
        "line_of_business": "professional_liability",
        "accident_year": 2023,
        "reserve_type": "ibnr",
        "carried_amount": 3_500_000,
        "indicated_amount": 3_800_000,
        "selected_amount": 3_600_000,
        "as_of_date": "2026-03-31",
        "analyst": "James Wright",
        "approved_by": "Michael Torres",
        "notes": "Long-tail development — monitoring closely.",
    },
]

_SEED_TRIANGLE_CYBER: list[dict[str, Any]] = [
    # Cyber triangle — accident years 2021-2024, dev months 12-60
    {"accident_year": 2021, "development_month": 12, "incurred_amount": 1_200_000, "paid_amount": 600_000, "case_reserve": 600_000, "claim_count": 15},
    {"accident_year": 2021, "development_month": 24, "incurred_amount": 2_100_000, "paid_amount": 1_400_000, "case_reserve": 700_000, "claim_count": 18},
    {"accident_year": 2021, "development_month": 36, "incurred_amount": 2_600_000, "paid_amount": 2_000_000, "case_reserve": 600_000, "claim_count": 19},
    {"accident_year": 2021, "development_month": 48, "incurred_amount": 2_800_000, "paid_amount": 2_500_000, "case_reserve": 300_000, "claim_count": 19},
    {"accident_year": 2021, "development_month": 60, "incurred_amount": 2_850_000, "paid_amount": 2_700_000, "case_reserve": 150_000, "claim_count": 19},
    {"accident_year": 2022, "development_month": 12, "incurred_amount": 1_500_000, "paid_amount": 700_000, "case_reserve": 800_000, "claim_count": 20},
    {"accident_year": 2022, "development_month": 24, "incurred_amount": 2_500_000, "paid_amount": 1_600_000, "case_reserve": 900_000, "claim_count": 24},
    {"accident_year": 2022, "development_month": 36, "incurred_amount": 3_100_000, "paid_amount": 2_400_000, "case_reserve": 700_000, "claim_count": 25},
    {"accident_year": 2022, "development_month": 48, "incurred_amount": 3_400_000, "paid_amount": 3_000_000, "case_reserve": 400_000, "claim_count": 25},
    {"accident_year": 2023, "development_month": 12, "incurred_amount": 1_800_000, "paid_amount": 800_000, "case_reserve": 1_000_000, "claim_count": 25},
    {"accident_year": 2023, "development_month": 24, "incurred_amount": 3_000_000, "paid_amount": 1_900_000, "case_reserve": 1_100_000, "claim_count": 30},
    {"accident_year": 2023, "development_month": 36, "incurred_amount": 3_800_000, "paid_amount": 2_800_000, "case_reserve": 1_000_000, "claim_count": 32},
    {"accident_year": 2024, "development_month": 12, "incurred_amount": 2_000_000, "paid_amount": 900_000, "case_reserve": 1_100_000, "claim_count": 28},
    {"accident_year": 2024, "development_month": 24, "incurred_amount": 3_400_000, "paid_amount": 2_100_000, "case_reserve": 1_300_000, "claim_count": 34},
]

_SEED_RATE_ADEQUACY: list[dict[str, Any]] = [
    {"line_of_business": "cyber", "segment": "smb-technology", "current_rate": "1.50", "indicated_rate": "1.72", "adequacy_ratio": "1.1467"},
    {"line_of_business": "cyber", "segment": "smb-healthcare", "current_rate": "2.20", "indicated_rate": "2.85", "adequacy_ratio": "1.2955"},
    {"line_of_business": "cyber", "segment": "smb-financial", "current_rate": "1.80", "indicated_rate": "1.95", "adequacy_ratio": "1.0833"},
    {"line_of_business": "cyber", "segment": "mid-market-technology", "current_rate": "1.20", "indicated_rate": "1.35", "adequacy_ratio": "1.1250"},
    {"line_of_business": "cyber", "segment": "mid-market-retail", "current_rate": "0.90", "indicated_rate": "0.82", "adequacy_ratio": "0.9111"},
    {"line_of_business": "professional_liability", "segment": "law-firms", "current_rate": "3.10", "indicated_rate": "3.45", "adequacy_ratio": "1.1129"},
    {"line_of_business": "professional_liability", "segment": "accounting", "current_rate": "2.50", "indicated_rate": "2.30", "adequacy_ratio": "0.9200"},
]


def _seed() -> None:
    if not _reserves:
        for r in _SEED_RESERVES:
            _reserves[r["id"]] = r
    if not _triangles:
        _triangles["cyber"] = _SEED_TRIANGLE_CYBER


_seed()


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
    _seed()
    items = list(_reserves.values())
    if lob:
        items = [r for r in items if r.get("line_of_business") == lob]
    if accident_year:
        items = [r for r in items if r.get("accident_year") == accident_year]
    return [ReserveResponse(**r) for r in items]


@router.post("/reserves", response_model=ReserveResponse, status_code=201)
async def set_reserve(body: ReserveCreate) -> ReserveResponse:
    """Create or update an actuarial reserve."""
    _seed()
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
    _reserves[rid] = record
    return ReserveResponse(**record)


@router.get("/triangles/{lob}", response_model=TriangleResponse)
async def get_loss_triangle(lob: str) -> TriangleResponse:
    """Get the loss-development triangle for a line of business."""
    _seed()
    entries = _triangles.get(lob, [])
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
    _seed()
    entries = _triangles.get(lob, [])
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
                (
                    e
                    for e in entries
                    if e["accident_year"] == ay and e["development_month"] == dm
                ),
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

    # Update in-memory store
    _triangles[lob] = generated

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
    _seed()
    items = _SEED_RATE_ADEQUACY
    if lob:
        items = [i for i in items if i.get("line_of_business") == lob]
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
    _seed()
    entries = _triangles.get(lob, [])
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
