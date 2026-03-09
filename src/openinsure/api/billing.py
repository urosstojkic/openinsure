"""Billing API endpoints for OpenInsure.

Manages billing accounts, invoices, and payment recording.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
_billing_accounts: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BillingAccountStatus(StrEnum):
    """Billing account lifecycle status."""

    ACTIVE = "active"
    PAID_IN_FULL = "paid_in_full"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    """Invoice payment status."""

    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"
    PAST_DUE = "past_due"


class PaymentMethod(StrEnum):
    """Payment method types."""

    ACH = "ach"
    WIRE = "wire"
    CHECK = "check"
    CREDIT_CARD = "credit_card"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BillingAccountCreate(BaseModel):
    """Payload for creating a billing account."""

    policy_id: str
    policyholder_name: str = Field(..., min_length=1, max_length=200)
    total_premium: float = Field(..., gt=0)
    installments: int = Field(1, ge=1, le=12, description="Number of installment payments")
    currency: str = "USD"
    billing_email: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BillingAccountResponse(BaseModel):
    """Public representation of a billing account."""

    id: str
    policy_id: str
    policyholder_name: str
    status: BillingAccountStatus
    total_premium: float
    total_paid: float
    balance_due: float
    installments: int
    currency: str
    billing_email: str | None = None
    payments: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class PaymentRequest(BaseModel):
    """Record a payment on a billing account."""

    amount: float = Field(..., gt=0)
    method: PaymentMethod
    reference: str | None = None
    notes: str | None = None


class PaymentResponse(BaseModel):
    """Result of recording a payment."""

    account_id: str
    payment_id: str
    amount: float
    method: PaymentMethod
    total_paid: float
    balance_due: float
    status: BillingAccountStatus
    created_at: str


class InvoiceCreate(BaseModel):
    """Payload for generating an invoice."""

    amount: float = Field(..., gt=0)
    due_date: str = Field(..., description="ISO-8601 due date")
    description: str = "Premium installment"
    line_items: list[dict[str, Any]] = Field(default_factory=list)


class InvoiceResponse(BaseModel):
    """Public representation of an invoice."""

    invoice_id: str
    account_id: str
    amount: float
    status: InvoiceStatus
    due_date: str
    description: str
    line_items: list[dict[str, Any]]
    created_at: str


class InvoiceList(BaseModel):
    """Paginated list of invoices for a billing account."""

    account_id: str
    items: list[InvoiceResponse]
    total: int
    skip: int
    limit: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_account(account_id: str) -> dict[str, Any]:
    account = _billing_accounts.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Billing account {account_id} not found")
    return account


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/accounts", response_model=BillingAccountResponse, status_code=201)
async def create_billing_account(body: BillingAccountCreate) -> BillingAccountResponse:
    """Create a billing account for a policy."""
    aid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": aid,
        "policy_id": body.policy_id,
        "policyholder_name": body.policyholder_name,
        "status": BillingAccountStatus.ACTIVE,
        "total_premium": body.total_premium,
        "total_paid": 0.0,
        "balance_due": body.total_premium,
        "installments": body.installments,
        "currency": body.currency,
        "billing_email": body.billing_email,
        "payments": [],
        "invoices": [],
        "metadata": body.metadata,
        "created_at": now,
        "updated_at": now,
    }
    _billing_accounts[aid] = record
    return BillingAccountResponse(**record)


@router.get("/accounts/{account_id}", response_model=BillingAccountResponse)
async def get_billing_account(account_id: str) -> BillingAccountResponse:
    """Retrieve a billing account by ID."""
    return BillingAccountResponse(**_get_account(account_id))


@router.post("/accounts/{account_id}/payment", response_model=PaymentResponse, status_code=201)
async def record_payment(account_id: str, body: PaymentRequest) -> PaymentResponse:
    """Record a payment against a billing account."""
    record = _get_account(account_id)
    if record["status"] == BillingAccountStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Cannot record payment on a cancelled account")
    if record["status"] == BillingAccountStatus.PAID_IN_FULL:
        raise HTTPException(status_code=409, detail="Account is already paid in full")

    pid = str(uuid.uuid4())
    now = _now()
    payment_entry: dict[str, Any] = {
        "payment_id": pid,
        "amount": body.amount,
        "method": body.method,
        "reference": body.reference,
        "notes": body.notes,
        "created_at": now,
    }
    record["payments"].append(payment_entry)
    record["total_paid"] = sum(p["amount"] for p in record["payments"])
    record["balance_due"] = max(0.0, record["total_premium"] - record["total_paid"])
    if record["balance_due"] == 0.0:
        record["status"] = BillingAccountStatus.PAID_IN_FULL
    record["updated_at"] = now

    return PaymentResponse(
        account_id=account_id,
        payment_id=pid,
        amount=body.amount,
        method=body.method,
        total_paid=record["total_paid"],
        balance_due=record["balance_due"],
        status=record["status"],
        created_at=now,
    )


@router.get("/accounts/{account_id}/invoices", response_model=InvoiceList)
async def list_invoices(
    account_id: str,
    status: InvoiceStatus | None = Query(None, description="Filter by invoice status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> InvoiceList:
    """List invoices for a billing account."""
    record = _get_account(account_id)
    invoices = record["invoices"]

    if status is not None:
        invoices = [i for i in invoices if i["status"] == status]

    total = len(invoices)
    page = invoices[skip : skip + limit]
    return InvoiceList(
        account_id=account_id,
        items=[InvoiceResponse(**i) for i in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/accounts/{account_id}/invoices", response_model=InvoiceResponse, status_code=201)
async def generate_invoice(account_id: str, body: InvoiceCreate) -> InvoiceResponse:
    """Generate an invoice on a billing account."""
    record = _get_account(account_id)
    if record["status"] == BillingAccountStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Cannot generate invoices on a cancelled account")

    iid = str(uuid.uuid4())
    now = _now()
    invoice_entry: dict[str, Any] = {
        "invoice_id": iid,
        "account_id": account_id,
        "amount": body.amount,
        "status": InvoiceStatus.ISSUED,
        "due_date": body.due_date,
        "description": body.description,
        "line_items": body.line_items,
        "created_at": now,
    }
    record["invoices"].append(invoice_entry)
    record["updated_at"] = now

    return InvoiceResponse(**invoice_entry)
