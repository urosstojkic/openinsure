"""Submission domain entities for OpenInsure.

Represents insurance applications flowing through the intake,
triage, underwriting, and quoting pipeline.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from openinsure.domain.common import (
    ConfidenceScore,
    DomainEntity,
    Money,
    Score,
    new_id,
)


class SubmissionStatus(StrEnum):
    """Lifecycle status of an insurance submission."""

    received = "received"
    triaging = "triaging"
    underwriting = "underwriting"
    referred = "referred"
    quoted = "quoted"
    bound = "bound"
    declined = "declined"
    expired = "expired"


class SubmissionChannel(StrEnum):
    """Channel through which a submission was received."""

    email = "email"
    api = "api"
    portal = "portal"
    broker_platform = "broker_platform"


class TriageResult(BaseModel):
    """Result of automated or manual triage of a submission."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    appetite_match: bool
    risk_score: Score
    priority: int = Field(ge=1, le=5)
    assigned_to: UUID | None = None
    decline_reason: str | None = None


class CyberRiskData(BaseModel):
    """Cyber-specific risk data extracted from a submission."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    annual_revenue: Money
    employee_count: int = Field(ge=0)
    industry_sic_code: str
    security_maturity_score: Score
    has_mfa: bool
    has_endpoint_protection: bool
    has_backup_strategy: bool
    has_incident_response_plan: bool
    prior_incidents: int = Field(ge=0)
    prior_breach_costs: Money | None = None
    tech_stack: list[str] | None = None


class Document(BaseModel):
    """A document attached to a submission."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    document_id: UUID = Field(default_factory=new_id)
    document_type: str = Field(
        ...,
        description=(
            "Document classification: acord_application, loss_run, financial_statement, supplemental, sov, prior_policy"
        ),
    )
    filename: str
    storage_url: str
    extracted_data: dict[str, Any] | None = None
    classification_confidence: ConfidenceScore | None = None


class Submission(DomainEntity):
    """An insurance application submitted for underwriting.

    Tracks the full lifecycle from receipt through triage, underwriting,
    quoting, and binding or decline.
    """

    submission_number: str
    status: SubmissionStatus = SubmissionStatus.received
    channel: SubmissionChannel
    line_of_business: str
    applicant: UUID = Field(description="Party ID of the applicant")
    broker: UUID | None = Field(default=None, description="Party ID of the submitting broker")
    documents: list[Document] = Field(default_factory=list)
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    cyber_risk_data: CyberRiskData | None = None
    triage_result: TriageResult | None = None

    # Coverage period
    requested_effective_date: date
    requested_expiration_date: date

    # Quoting
    quoted_premium: Money | None = None

    # Multi-currency support (#174)
    currency: str = Field(default="USD", max_length=3)

    # Rating factor version tracking (#181)
    rated_with_snapshot_id: str | None = None

    # Status transition timestamps
    received_at: datetime | None = None
    triaging_at: datetime | None = None
    underwriting_at: datetime | None = None
    quoted_at: datetime | None = None
    bound_at: datetime | None = None
    referred_at: datetime | None = None
    declined_at: datetime | None = None
    expired_at: datetime | None = None
