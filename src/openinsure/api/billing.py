"""Billing API endpoints for OpenInsure.

Manages billing accounts, invoices, payment recording, and ledger history.
Uses in-memory storage as a placeholder until the database adapter is wired in.

Addresses #77: Billing Pipeline API & AI-Native Billing Agent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_billing_repository

router = APIRouter()
logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_billing_repository()


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


class LedgerEntry(BaseModel):
    """A single ledger transaction."""

    entry_id: str
    account_id: str
    entry_type: str  # invoice_issued | payment_received | invoice_voided
    amount: float
    balance_after: float
    description: str
    reference_id: str
    created_at: str


class LedgerResponse(BaseModel):
    """Transaction history for a billing account."""

    account_id: str
    entries: list[LedgerEntry]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_account(account_id: str) -> dict[str, Any]:
    account = await _repo.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Billing account {account_id} not found")
    return account


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _build_ledger(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a chronological ledger from invoices and payments."""
    entries: list[dict[str, Any]] = []
    for inv in record.get("invoices", []):
        entries.append(
            {
                "entry_type": "invoice_issued",
                "amount": inv["amount"],
                "description": inv.get("description", "Invoice"),
                "reference_id": inv["invoice_id"],
                "created_at": inv["created_at"],
            }
        )
    for pmt in record.get("payments", []):
        entries.append(
            {
                "entry_type": "payment_received",
                "amount": -pmt["amount"],
                "description": f"Payment via {pmt.get('method', 'unknown')}",
                "reference_id": pmt["payment_id"],
                "created_at": pmt["created_at"],
            }
        )
    entries.sort(key=lambda e: e["created_at"])

    # Compute running balance
    balance = 0.0
    for entry in entries:
        balance += entry["amount"]
        entry["balance_after"] = round(balance, 2)
    return entries


# ---------------------------------------------------------------------------
# Auto-invoice on bind helper (called from submissions.py)
# ---------------------------------------------------------------------------


async def create_billing_account_on_bind(
    *,
    policy_id: str,
    policyholder_name: str,
    total_premium: float,
    installments: int = 1,
    effective_date: str | None = None,
) -> dict[str, Any]:
    """Create a billing account and first invoice(s) when a policy is bound.

    If ``installments > 1``, generates an installment schedule with evenly
    spaced due dates across the policy term (default: quarterly).
    """
    aid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": aid,
        "policy_id": policy_id,
        "policyholder_name": policyholder_name,
        "status": BillingAccountStatus.ACTIVE,
        "total_premium": total_premium,
        "total_paid": 0.0,
        "balance_due": total_premium,
        "installments": installments,
        "currency": "USD",
        "billing_email": None,
        "payments": [],
        "invoices": [],
        "metadata": {"auto_created": True, "source": "policy_bind"},
        "created_at": now,
        "updated_at": now,
    }

    # Generate invoice schedule
    base_date = datetime.fromisoformat(effective_date) if effective_date else datetime.now(UTC)
    installment_amount = round(total_premium / installments, 2)
    remainder = round(total_premium - installment_amount * installments, 2)

    for i in range(installments):
        due = base_date + timedelta(days=30 * i)
        amount = installment_amount + (remainder if i == 0 else 0.0)
        inv_id = str(uuid.uuid4())
        inv_num = i + 1
        record["invoices"].append(
            {
                "invoice_id": inv_id,
                "account_id": aid,
                "amount": round(amount, 2),
                "status": InvoiceStatus.ISSUED,
                "due_date": due.strftime("%Y-%m-%d"),
                "description": f"Premium installment {inv_num}/{installments}"
                if installments > 1
                else "Full premium payment",
                "line_items": [
                    {
                        "item": "Premium",
                        "amount": round(amount, 2),
                        "installment": inv_num,
                        "total_installments": installments,
                    }
                ],
                "created_at": now,
            }
        )

    await _repo.create(record)
    logger.info(
        "billing.account_created_on_bind",
        account_id=aid,
        policy_id=policy_id,
        installments=installments,
        total_premium=total_premium,
    )
    return record


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
    await _repo.create(record)
    return BillingAccountResponse(**record)


@router.get("/accounts/{account_id}", response_model=BillingAccountResponse)
async def get_billing_account(account_id: str) -> BillingAccountResponse:
    """Retrieve a billing account by ID."""
    return BillingAccountResponse(**await _get_account(account_id))


@router.post("/accounts/{account_id}/payments", response_model=PaymentResponse, status_code=201)
async def record_payment(account_id: str, body: PaymentRequest) -> PaymentResponse:
    """Record a payment against a billing account."""
    record = await _get_account(account_id)
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

    # Auto-mark matching invoices as paid
    remaining = body.amount
    for inv in record.get("invoices", []):
        if inv["status"] == InvoiceStatus.ISSUED and remaining >= inv["amount"]:
            inv["status"] = InvoiceStatus.PAID
            remaining -= inv["amount"]
            if remaining <= 0:
                break

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


# Keep the old path working as an alias
@router.post("/accounts/{account_id}/payment", response_model=PaymentResponse, status_code=201, include_in_schema=False)
async def record_payment_alias(account_id: str, body: PaymentRequest) -> PaymentResponse:
    """Alias for backward compatibility."""
    return await record_payment(account_id, body)


@router.get("/accounts/{account_id}/invoices", response_model=InvoiceList)
async def list_invoices(
    account_id: str,
    status: InvoiceStatus | None = Query(None, description="Filter by invoice status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> InvoiceList:
    """List invoices for a billing account."""
    record = await _get_account(account_id)
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
    record = await _get_account(account_id)
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


@router.get("/accounts/{account_id}/ledger", response_model=LedgerResponse)
async def get_ledger(account_id: str) -> LedgerResponse:
    """Return chronological transaction history for a billing account."""
    record = await _get_account(account_id)
    raw_entries = _build_ledger(record)
    entries = [
        LedgerEntry(
            entry_id=str(uuid.uuid4()),
            account_id=account_id,
            **e,
        )
        for e in raw_entries
    ]
    return LedgerResponse(account_id=account_id, entries=entries, total=len(entries))
