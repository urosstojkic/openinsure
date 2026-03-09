"""Billing domain entities for OpenInsure.

Represents billing accounts, invoices, payment schedules,
and broker commission records.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from openinsure.domain.common import DomainEntity, Money, Percentage


class BillingPlan(StrEnum):
    """Available billing plan types."""

    full_pay = "full_pay"
    quarterly = "quarterly"
    monthly = "monthly"
    agency_bill = "agency_bill"
    direct_bill = "direct_bill"


class PaymentStatus(StrEnum):
    """Status of an individual payment or installment."""

    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"
    refunded = "refunded"


class InvoiceStatus(StrEnum):
    """Lifecycle status of an invoice."""

    draft = "draft"
    issued = "issued"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"
    void = "void"


class BillingScheduleEntry(BaseModel):
    """A single installment in a billing schedule."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    due_date: date
    amount: Money
    status: PaymentStatus = PaymentStatus.pending
    paid_date: date | None = None
    paid_amount: Money | None = None


class LineItem(BaseModel):
    """A single line item on an invoice."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    description: str
    amount: Money


class Invoice(BaseModel):
    """An invoice issued for premium or fees."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    invoice_number: str
    policy_id: UUID
    status: InvoiceStatus = InvoiceStatus.draft
    issue_date: date
    due_date: date
    amount: Money
    paid_amount: Money = Decimal("0.00")
    line_items: list[LineItem] = Field(default_factory=list)


class CommissionRecord(BaseModel):
    """A commission earned by a broker on a policy."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    broker_id: UUID
    policy_id: UUID
    commission_rate: Percentage
    commission_amount: Money
    paid: bool = False
    paid_date: date | None = None


class BillingAccount(DomainEntity):
    """Billing account for a policy.

    Tracks the billing plan, installment schedule, invoices, and
    broker commissions. The ``balance_due`` computed field reflects
    the outstanding premium balance.
    """

    policy_id: UUID
    billing_plan: BillingPlan
    total_premium: Money

    # Schedule and invoices
    installments: list[BillingScheduleEntry] = Field(default_factory=list)
    invoices: list[Invoice] = Field(default_factory=list)
    commissions: list[CommissionRecord] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def balance_due(self) -> Decimal:
        """Outstanding balance: total premium minus all payments received."""
        total_paid = sum(
            (entry.paid_amount for entry in self.installments if entry.paid_amount is not None),
            Decimal("0.00"),
        )
        return self.total_premium - total_paid
