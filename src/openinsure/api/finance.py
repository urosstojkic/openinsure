"""Finance dashboard API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Mock financial data
# ---------------------------------------------------------------------------

_FINANCIAL_SUMMARY = {
    "premium_written": 24_500_000,
    "premium_earned": 18_200_000,
    "premium_unearned": 6_300_000,
    "claims_paid": 8_100_000,
    "claims_reserved": 4_600_000,
    "claims_incurred": 12_700_000,
    "loss_ratio": 0.5306,
    "expense_ratio": 0.32,
    "combined_ratio": 0.8506,
    "investment_income": 1_200_000,
    "operating_income": 3_900_000,
}

_CASHFLOW_MONTHS = [
    {"month": "2025-07", "collections": 2_100_000, "disbursements": 1_500_000, "net": 600_000},
    {"month": "2025-08", "collections": 2_300_000, "disbursements": 1_700_000, "net": 600_000},
    {"month": "2025-09", "collections": 1_900_000, "disbursements": 1_800_000, "net": 100_000},
    {"month": "2025-10", "collections": 2_400_000, "disbursements": 1_600_000, "net": 800_000},
    {"month": "2025-11", "collections": 2_200_000, "disbursements": 2_000_000, "net": 200_000},
    {"month": "2025-12", "collections": 2_600_000, "disbursements": 1_900_000, "net": 700_000},
    {"month": "2026-01", "collections": 2_000_000, "disbursements": 1_400_000, "net": 600_000},
    {"month": "2026-02", "collections": 2_100_000, "disbursements": 1_600_000, "net": 500_000},
    {"month": "2026-03", "collections": 2_500_000, "disbursements": 1_800_000, "net": 700_000},
    {"month": "2026-04", "collections": 2_300_000, "disbursements": 2_100_000, "net": 200_000},
    {"month": "2026-05", "collections": 2_700_000, "disbursements": 1_700_000, "net": 1_000_000},
    {"month": "2026-06", "collections": 2_400_000, "disbursements": 1_900_000, "net": 500_000},
]

_COMMISSIONS = [
    {
        "broker": "Marsh & Co",
        "policies": 42,
        "premium": 4_200_000,
        "commission_rate": 0.12,
        "commission_amount": 504_000,
        "status": "paid",
    },
    {
        "broker": "Aon Risk Solutions",
        "policies": 35,
        "premium": 3_600_000,
        "commission_rate": 0.10,
        "commission_amount": 360_000,
        "status": "paid",
    },
    {
        "broker": "Willis Towers Watson",
        "policies": 28,
        "premium": 2_900_000,
        "commission_rate": 0.11,
        "commission_amount": 319_000,
        "status": "pending",
    },
    {
        "broker": "Brown & Brown",
        "policies": 18,
        "premium": 1_800_000,
        "commission_rate": 0.10,
        "commission_amount": 180_000,
        "status": "pending",
    },
    {
        "broker": "Gallagher",
        "policies": 22,
        "premium": 2_200_000,
        "commission_rate": 0.09,
        "commission_amount": 198_000,
        "status": "overdue",
    },
]

_RECONCILIATION = [
    {
        "item": "Premium receivables",
        "expected": 6_300_000,
        "actual": 6_100_000,
        "variance": -200_000,
        "status": "warning",
    },
    {"item": "Claims payables", "expected": 4_600_000, "actual": 4_600_000, "variance": 0, "status": "matched"},
    {"item": "Commission payables", "expected": 1_561_000, "actual": 1_561_000, "variance": 0, "status": "matched"},
    {
        "item": "Reinsurance recoverables",
        "expected": 2_100_000,
        "actual": 1_950_000,
        "variance": -150_000,
        "status": "warning",
    },
    {"item": "Tax reserves", "expected": 780_000, "actual": 780_000, "variance": 0, "status": "matched"},
]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class FinancialSummary(BaseModel):
    premium_written: float
    premium_earned: float
    premium_unearned: float
    claims_paid: float
    claims_reserved: float
    claims_incurred: float
    loss_ratio: float
    expense_ratio: float
    combined_ratio: float
    investment_income: float
    operating_income: float


class CashFlowMonth(BaseModel):
    month: str
    collections: float
    disbursements: float
    net: float


class CashFlowResponse(BaseModel):
    months: list[CashFlowMonth]
    total_collections: float
    total_disbursements: float
    net_cash_flow: float


class CommissionEntry(BaseModel):
    broker: str
    policies: int
    premium: float
    commission_rate: float
    commission_amount: float
    status: str


class CommissionSummary(BaseModel):
    total_commissions: float
    paid: float
    pending: float
    overdue: float
    entries: list[CommissionEntry]


class ReconciliationItem(BaseModel):
    item: str
    expected: float
    actual: float
    variance: float
    status: str


class BordereauGenerateRequest(BaseModel):
    mga_id: str
    period: str


class BordereauGenerateResponse(BaseModel):
    id: str
    mga_id: str
    period: str
    premium_total: float
    claims_total: float
    policy_count: int
    generated_at: str
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=FinancialSummary)
async def financial_summary() -> FinancialSummary:
    """Financial summary: premium written/earned/unearned, claims paid/reserved."""
    return FinancialSummary(**_FINANCIAL_SUMMARY)


@router.get("/cashflow", response_model=CashFlowResponse)
async def cash_flow() -> CashFlowResponse:
    """Cash flow: collections vs disbursements over 12 months."""
    total_c = sum(m["collections"] for m in _CASHFLOW_MONTHS)
    total_d = sum(m["disbursements"] for m in _CASHFLOW_MONTHS)
    return CashFlowResponse(
        months=[CashFlowMonth(**m) for m in _CASHFLOW_MONTHS],
        total_collections=total_c,
        total_disbursements=total_d,
        net_cash_flow=total_c - total_d,
    )


@router.get("/commissions", response_model=CommissionSummary)
async def commissions() -> CommissionSummary:
    """Commission summary by broker."""
    entries = [CommissionEntry(**c) for c in _COMMISSIONS]
    total = sum(c["commission_amount"] for c in _COMMISSIONS)
    paid = sum(c["commission_amount"] for c in _COMMISSIONS if c["status"] == "paid")
    pending = sum(c["commission_amount"] for c in _COMMISSIONS if c["status"] == "pending")
    overdue = sum(c["commission_amount"] for c in _COMMISSIONS if c["status"] == "overdue")
    return CommissionSummary(
        total_commissions=total,
        paid=paid,
        pending=pending,
        overdue=overdue,
        entries=entries,
    )


@router.get("/reconciliation", response_model=list[ReconciliationItem])
async def reconciliation() -> list[ReconciliationItem]:
    """Reconciliation status for key financial items."""
    return [ReconciliationItem(**r) for r in _RECONCILIATION]


@router.post("/bordereaux/generate", response_model=BordereauGenerateResponse, status_code=201)
async def generate_bordereau(body: BordereauGenerateRequest) -> BordereauGenerateResponse:
    """Generate an MGA bordereau report."""
    bid = f"bx-gen-{uuid.uuid4().hex[:8]}"
    return BordereauGenerateResponse(
        id=bid,
        mga_id=body.mga_id,
        period=body.period,
        premium_total=820_000,
        claims_total=340_000,
        policy_count=145,
        generated_at=datetime.now(UTC).isoformat(),
        status="generated",
    )
