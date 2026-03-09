"""Claim domain entities for OpenInsure.

Represents insurance claims from first notice of loss through
investigation, reserving, settlement, and closure.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from openinsure.domain.common import ConfidenceScore, DomainEntity, Money, new_id


class ClaimStatus(StrEnum):
    """Lifecycle status of a claim."""

    fnol = "fnol"
    investigating = "investigating"
    reserved = "reserved"
    settling = "settling"
    closed = "closed"
    reopened = "reopened"
    denied = "denied"


class SeverityTier(StrEnum):
    """Severity classification for a claim."""

    simple = "simple"
    moderate = "moderate"
    complex = "complex"
    catastrophe = "catastrophe"


class CauseOfLoss(StrEnum):
    """Categorization of the cause of loss."""

    data_breach = "data_breach"
    ransomware = "ransomware"
    social_engineering = "social_engineering"
    system_failure = "system_failure"
    unauthorized_access = "unauthorized_access"
    denial_of_service = "denial_of_service"
    other = "other"


class Reserve(BaseModel):
    """A financial reserve set aside for a claim."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    reserve_type: str = Field(..., description="Reserve category: indemnity, expense")
    amount: Money
    set_date: datetime
    set_by: str = Field(..., description="Who set the reserve: agent or human")
    confidence: ConfidenceScore


class Payment(BaseModel):
    """A payment issued against a claim."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    payment_id: UUID = Field(default_factory=new_id)
    amount: Money
    payee_id: UUID
    payment_date: datetime
    payment_type: str = Field(
        ...,
        description="Payment category: indemnity, expense, deductible_recovery",
    )


class ClaimDocument(BaseModel):
    """A document associated with a claim."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    document_type: str = Field(
        ...,
        description=("Document classification: fnol_report, adjuster_notes, invoice, settlement, denial_letter"),
    )
    storage_url: str
    uploaded_at: datetime


class Claim(DomainEntity):
    """An insurance claim filed against a policy.

    Tracks the claim from first notice of loss through investigation,
    reserving, payment, and closure. The ``total_incurred`` computed
    field reflects the sum of all reserves and payments.
    """

    claim_number: str
    status: ClaimStatus = ClaimStatus.fnol
    policy_id: UUID

    # Loss details
    loss_date: date
    report_date: date
    loss_type: str
    cause_of_loss: CauseOfLoss
    description: str
    severity: SeverityTier

    # Parties
    claimant_ids: list[UUID] = Field(default_factory=list)

    # Financial
    reserves: list[Reserve] = Field(default_factory=list)
    payments: list[Payment] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_incurred(self) -> Decimal:
        """Total incurred amount: sum of all reserve amounts plus payments."""
        reserve_total = sum((r.amount for r in self.reserves), Decimal("0.00"))
        payment_total = sum((p.amount for p in self.payments), Decimal("0.00"))
        return reserve_total + payment_total

    # Documents
    documents: list[ClaimDocument] = Field(default_factory=list)

    # Assignment and scoring
    assigned_adjuster: UUID | None = None
    fraud_score: ConfidenceScore | None = None

    # Closure
    closed_at: datetime | None = None
    close_reason: str | None = None
