"""Tests for billing API endpoints and auto-invoice on bind (#77)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from openinsure.api.billing import (
    BillingAccountCreate,
    BillingAccountStatus,
    InvoiceCreate,
    InvoiceStatus,
    PaymentMethod,
    PaymentRequest,
    _build_ledger,
    create_billing_account_on_bind,
)

# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestBillingModels:
    def test_billing_account_create_requires_positive_premium(self) -> None:
        with pytest.raises(Exception):
            BillingAccountCreate(
                policy_id="pol-1",
                policyholder_name="Acme",
                total_premium=0,
            )

    def test_billing_account_create_defaults(self) -> None:
        body = BillingAccountCreate(
            policy_id="pol-1",
            policyholder_name="Acme Corp",
            total_premium=10000.0,
        )
        assert body.installments == 1
        assert body.currency == "USD"
        assert body.billing_email is None

    def test_payment_request_requires_positive_amount(self) -> None:
        with pytest.raises(Exception):
            PaymentRequest(amount=-100, method=PaymentMethod.ACH)

    def test_invoice_create_defaults(self) -> None:
        body = InvoiceCreate(amount=5000.0, due_date="2025-06-01")
        assert body.description == "Premium installment"
        assert body.line_items == []


# ---------------------------------------------------------------------------
# Ledger builder
# ---------------------------------------------------------------------------


class TestBuildLedger:
    def test_empty_account(self) -> None:
        record: dict[str, Any] = {"invoices": [], "payments": []}
        entries = _build_ledger(record)
        assert entries == []

    def test_invoice_only(self) -> None:
        record: dict[str, Any] = {
            "invoices": [
                {"invoice_id": "inv-1", "amount": 5000, "description": "Premium", "created_at": "2025-01-01T00:00:00"}
            ],
            "payments": [],
        }
        entries = _build_ledger(record)
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "invoice_issued"
        assert entries[0]["balance_after"] == 5000

    def test_invoice_plus_payment(self) -> None:
        record: dict[str, Any] = {
            "invoices": [
                {"invoice_id": "inv-1", "amount": 5000, "description": "Premium", "created_at": "2025-01-01T00:00:00"}
            ],
            "payments": [{"payment_id": "pmt-1", "amount": 5000, "method": "ach", "created_at": "2025-01-15T00:00:00"}],
        }
        entries = _build_ledger(record)
        assert len(entries) == 2
        assert entries[0]["entry_type"] == "invoice_issued"
        assert entries[1]["entry_type"] == "payment_received"
        assert entries[1]["balance_after"] == 0.0

    def test_partial_payment(self) -> None:
        record: dict[str, Any] = {
            "invoices": [
                {"invoice_id": "inv-1", "amount": 10000, "description": "Premium", "created_at": "2025-01-01T00:00:00"}
            ],
            "payments": [
                {"payment_id": "pmt-1", "amount": 3000, "method": "check", "created_at": "2025-01-15T00:00:00"}
            ],
        }
        entries = _build_ledger(record)
        assert entries[1]["balance_after"] == 7000.0


# ---------------------------------------------------------------------------
# Auto-invoice on bind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateBillingAccountOnBind:
    @patch("openinsure.api.billing._repo")
    async def test_single_installment(self, mock_repo: Any) -> None:
        mock_repo.create = AsyncMock()
        result = await create_billing_account_on_bind(
            policy_id="pol-001",
            policyholder_name="Acme Corp",
            total_premium=12000.0,
            installments=1,
            effective_date="2025-01-15T00:00:00+00:00",
        )
        assert result["policy_id"] == "pol-001"
        assert result["status"] == BillingAccountStatus.ACTIVE
        assert result["total_premium"] == 12000.0
        assert result["balance_due"] == 12000.0
        assert len(result["invoices"]) == 1
        assert result["invoices"][0]["amount"] == 12000.0
        assert result["invoices"][0]["description"] == "Full premium payment"

    @patch("openinsure.api.billing._repo")
    async def test_quarterly_installments(self, mock_repo: Any) -> None:
        mock_repo.create = AsyncMock()
        result = await create_billing_account_on_bind(
            policy_id="pol-002",
            policyholder_name="Beta Inc",
            total_premium=10000.0,
            installments=4,
        )
        assert len(result["invoices"]) == 4
        total_invoiced = sum(inv["amount"] for inv in result["invoices"])
        assert abs(total_invoiced - 10000.0) < 0.02

    @patch("openinsure.api.billing._repo")
    async def test_monthly_installments(self, mock_repo: Any) -> None:
        mock_repo.create = AsyncMock()
        result = await create_billing_account_on_bind(
            policy_id="pol-003",
            policyholder_name="Gamma LLC",
            total_premium=12000.0,
            installments=12,
        )
        assert len(result["invoices"]) == 12
        for inv in result["invoices"]:
            assert inv["status"] == InvoiceStatus.ISSUED

    @patch("openinsure.api.billing._repo")
    async def test_metadata_marks_auto_created(self, mock_repo: Any) -> None:
        mock_repo.create = AsyncMock()
        result = await create_billing_account_on_bind(
            policy_id="pol-004",
            policyholder_name="Delta Co",
            total_premium=5000.0,
        )
        assert result["metadata"]["auto_created"] is True
        assert result["metadata"]["source"] == "policy_bind"
