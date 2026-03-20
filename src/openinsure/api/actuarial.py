"""Actuarial API — reserves, triangles & rate adequacy derived from claim/policy data.

All numbers come from the claim and policy repositories so that actuarial
views stay consistent with the executive and finance dashboards.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from openinsure.infrastructure.factory import (
    get_claim_repository,
    get_policy_repository,
    get_submission_repository,
)
from openinsure.services.actuarial import (
    Triangle,
    estimate_ibnr,
)

router = APIRouter()


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _policy_premium(p: dict[str, Any]) -> float:
    return float(p.get("premium", 0) or p.get("total_premium", 0) or 0)


async def _load_lob_mappings() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    """Return (claims, policies, submissions, policy_id->lob mapping)."""
    sub_repo = get_submission_repository()
    pol_repo = get_policy_repository()
    clm_repo = get_claim_repository()

    subs = await sub_repo.list_all(limit=5000)
    pols = await pol_repo.list_all(limit=5000)
    claims = await clm_repo.list_all(limit=5000)

    sub_lob: dict[str, str] = {s["id"]: s.get("line_of_business", "cyber") for s in subs}
    pol_lob: dict[str, str] = {}
    for p in pols:
        lob = p.get("lob") or sub_lob.get(p.get("submission_id", ""), "cyber")
        pol_lob[p["id"]] = lob
    return claims, pols, subs, pol_lob


def _claim_lob(c: dict[str, Any], pol_lob: dict[str, str]) -> str:
    return c.get("lob") or c.get("line_of_business") or pol_lob.get(c.get("policy_id", ""), "cyber")


def _claim_accident_year(c: dict[str, Any]) -> int:
    dol = str(c.get("date_of_loss", "") or c.get("loss_date", ""))
    try:
        return int(dol[:4])
    except (ValueError, IndexError):
        return datetime.now(UTC).year


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
# Internal: build a loss-development triangle from claims
# ---------------------------------------------------------------------------

# Standard cumulative development pattern (% of ultimate at each period)
_DEV_PATTERN: dict[int, float] = {12: 0.55, 24: 0.75, 36: 0.88, 48: 0.95, 60: 1.00}


def _build_triangle_entries(
    lob_claims: list[dict[str, Any]],
    pol_lob: dict[str, str],
) -> list[dict[str, Any]]:
    """Construct triangle entries from claims for one LOB."""
    now = datetime.now(UTC)

    # Aggregate by accident year
    ay_data: dict[int, dict[str, float | int]] = {}
    for c in lob_claims:
        ay = _claim_accident_year(c)
        if ay not in ay_data:
            ay_data[ay] = {"incurred": 0.0, "paid": 0.0, "reserved": 0.0, "count": 0}
        ay_data[ay]["incurred"] += float(c.get("total_incurred", 0) or 0)
        ay_data[ay]["paid"] += float(c.get("total_paid", 0) or 0)
        ay_data[ay]["reserved"] += float(c.get("total_reserved", 0) or 0)
        ay_data[ay]["count"] += 1

    entries: list[dict[str, Any]] = []
    for ay in sorted(ay_data):
        data = ay_data[ay]
        months_elapsed = (now.year - ay) * 12 + now.month
        current_dev = max(12, (months_elapsed // 12) * 12)
        current_dev = min(current_dev, 60)
        current_pct = _DEV_PATTERN.get(current_dev, 1.0)

        current_incurred = float(data["incurred"])
        ultimate = current_incurred / current_pct if current_pct > 0 else current_incurred

        for dm, pct in sorted(_DEV_PATTERN.items()):
            if dm > current_dev:
                break
            ratio = pct / current_pct if current_pct > 0 else 1.0
            entries.append(
                {
                    "accident_year": ay,
                    "development_month": dm,
                    "incurred_amount": round(ultimate * pct, 2),
                    "paid_amount": round(float(data["paid"]) * ratio, 2),
                    "case_reserve": round(float(data["reserved"]) * ratio, 2),
                    "claim_count": int(data["count"]),
                }
            )
    return entries


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/reserves", response_model=list[ReserveResponse])
async def list_reserves(
    lob: str | None = Query(None, description="Filter by line of business"),
    accident_year: int | None = Query(None, description="Filter by accident year"),
) -> list[ReserveResponse]:
    """Actuarial reserves derived from SUM(total_reserved) on actual claims."""
    claims, _pols, _subs, pol_lob = await _load_lob_mappings()

    groups: dict[tuple[str, int], dict[str, float | int]] = {}
    for c in claims:
        c_lob = _claim_lob(c, pol_lob)
        ay = _claim_accident_year(c)
        key = (c_lob, ay)
        if key not in groups:
            groups[key] = {"reserved": 0.0, "paid": 0.0, "incurred": 0.0, "count": 0}
        groups[key]["reserved"] += float(c.get("total_reserved", 0) or 0)
        groups[key]["paid"] += float(c.get("total_paid", 0) or 0)
        groups[key]["incurred"] += float(c.get("total_incurred", 0) or 0)
        groups[key]["count"] += 1

    if lob:
        groups = {k: v for k, v in groups.items() if k[0] == lob}
    if accident_year:
        groups = {k: v for k, v in groups.items() if k[1] == accident_year}

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    reserves: list[ReserveResponse] = []
    for (g_lob, g_ay), data in sorted(groups.items()):
        reserves.append(
            ReserveResponse(
                id=f"res-{g_lob[:3]}-{g_ay}-case",
                line_of_business=g_lob,
                accident_year=g_ay,
                reserve_type="case",
                carried_amount=round(float(data["reserved"]), 2),
                indicated_amount=round(float(data["incurred"]), 2),
                selected_amount=round(float(data["reserved"]), 2),
                as_of_date=today,
                analyst="System",
                approved_by="",
                notes=f"{int(data['count'])} claims",
            )
        )
    return reserves


@router.post("/reserves", response_model=ReserveResponse, status_code=201)
async def set_reserve(body: ReserveCreate) -> ReserveResponse:
    """Create a manual actuarial reserve override."""
    from openinsure.infrastructure.factory import get_actuarial_reserve_repository

    reserve_repo = get_actuarial_reserve_repository()
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
    await reserve_repo.create(record)
    return ReserveResponse(**record)


@router.get("/triangles/{lob}", response_model=TriangleResponse)
async def get_loss_triangle(lob: str) -> TriangleResponse:
    """Loss-development triangle built from actual claims for the LOB."""
    claims, _pols, _subs, pol_lob = await _load_lob_mappings()

    lob_claims = [c for c in claims if _claim_lob(c, pol_lob) == lob]
    if not lob_claims:
        raise HTTPException(status_code=404, detail=f"No claims data for LOB '{lob}'")

    entries = _build_triangle_entries(lob_claims, pol_lob)
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
    """Re-generate a loss triangle from claims data for the LOB."""
    return await get_loss_triangle(lob)


@router.get("/rate-adequacy", response_model=RateAdequacyResponse)
async def rate_adequacy(
    lob: str | None = Query(None, description="Filter by line of business"),
) -> RateAdequacyResponse:
    """Rate adequacy: actual loss ratio vs target rate by LOB segment."""
    claims, pols, subs, pol_lob = await _load_lob_mappings()

    sub_lob: dict[str, str] = {s["id"]: s.get("line_of_business", "cyber") for s in subs}

    # Premium by LOB
    lob_premium: dict[str, float] = {}
    for p in pols:
        p_lob = p.get("lob") or sub_lob.get(p.get("submission_id", ""), "cyber")
        lob_premium[p_lob] = lob_premium.get(p_lob, 0) + _policy_premium(p)

    # Incurred by LOB
    lob_incurred: dict[str, float] = {}
    for c in claims:
        c_lob = _claim_lob(c, pol_lob)
        lob_incurred[c_lob] = lob_incurred.get(c_lob, 0) + float(c.get("total_incurred", 0) or 0)

    target_loss_ratio = Decimal("0.60")
    all_lobs = sorted(set(list(lob_premium.keys()) + list(lob_incurred.keys())))

    if lob:
        all_lobs = [x for x in all_lobs if x == lob]

    items: list[RateAdequacyItem] = []
    for lob_name in all_lobs:
        prem = lob_premium.get(lob_name, 0)
        inc = lob_incurred.get(lob_name, 0)
        actual_lr = Decimal(str(round(inc / prem, 4))) if prem > 0 else Decimal("0")
        # Indicated rate adjustment = actual_lr / target_lr
        adequacy = (
            (actual_lr / target_loss_ratio).quantize(Decimal("0.0001"))
            if target_loss_ratio > 0
            else Decimal("0")
        )
        display = lob_name.replace("_", " ").title()
        items.append(
            RateAdequacyItem(
                line_of_business=lob_name,
                segment=display,
                current_rate=str(target_loss_ratio),
                indicated_rate=str(actual_lr),
                adequacy_ratio=str(adequacy),
            )
        )

    return RateAdequacyResponse(items=items, total=len(items))


@router.get("/ibnr/{lob}", response_model=IBNRResponse)
async def get_ibnr(
    lob: str,
    method: str = Query("chain_ladder", description="IBNR estimation method"),
) -> IBNRResponse:
    """IBNR estimate using chain-ladder on claims-derived triangle."""
    claims, _pols, _subs, pol_lob = await _load_lob_mappings()

    lob_claims = [c for c in claims if _claim_lob(c, pol_lob) == lob]
    if not lob_claims:
        raise HTTPException(status_code=404, detail=f"No claims data for LOB '{lob}'")

    entries = _build_triangle_entries(lob_claims, pol_lob)
    if not entries:
        raise HTTPException(status_code=404, detail=f"No triangle data for LOB '{lob}'")

    # Build Triangle dict for the actuarial service
    triangle: Triangle = {}
    for e in entries:
        ay = e["accident_year"]
        dm = e["development_month"]
        amt = Decimal(str(e["incurred_amount"]))
        triangle.setdefault(ay, {})[dm] = amt

    result = estimate_ibnr(triangle, method=method)

    return IBNRResponse(line_of_business=lob, method=method, **result)
