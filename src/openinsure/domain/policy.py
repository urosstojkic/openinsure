"""Policy domain entities for OpenInsure.

Represents insurance contracts including coverages, endorsements,
and policy documents.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from openinsure.domain.common import DomainEntity, Money


class PolicyStatus(StrEnum):
    """Lifecycle status of an insurance policy."""

    active = "active"
    expired = "expired"
    cancelled = "cancelled"
    pending = "pending"
    suspended = "suspended"
    reinstated = "reinstated"


class Coverage(BaseModel):
    """A coverage within an insurance policy."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    coverage_code: str
    coverage_name: str
    limit: Money
    deductible: Money
    premium: Money
    sublimits: dict[str, Decimal] | None = None


class Endorsement(BaseModel):
    """A modification to an existing policy."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    endorsement_number: str
    effective_date: date
    description: str
    premium_change: Decimal = Field(description="Premium adjustment; may be negative for credits")
    coverages_modified: list[str] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    """A document associated with a policy."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    document_type: str = Field(
        ...,
        description=("Document classification: declarations, policy_form, endorsement, certificate"),
    )
    generated_at: datetime
    storage_url: str


class Policy(DomainEntity):
    """An insurance contract between the carrier and insured.

    Tracks coverages, endorsements, premiums, and the full policy
    document set throughout the policy lifecycle.
    """

    policy_number: str
    status: PolicyStatus = PolicyStatus.pending
    product_id: UUID
    submission_id: UUID
    insured_id: UUID
    broker_id: UUID | None = None

    # Coverage period
    effective_date: date
    expiration_date: date

    # Coverages and endorsements
    coverages: list[Coverage] = Field(default_factory=list)
    endorsements: list[Endorsement] = Field(default_factory=list)

    # Premiums
    total_premium: Money
    written_premium: Money
    earned_premium: Money
    unearned_premium: Money

    # Documents
    documents: list[PolicyDocument] = Field(default_factory=list)

    # Lifecycle timestamps
    bound_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    reinstated_at: datetime | None = None
