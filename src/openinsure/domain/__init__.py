"""OpenInsure domain entities.

Re-exports all domain models, enums, and type aliases for convenient access::

    from openinsure.domain import Party, Policy, Claim, Submission
"""

from openinsure.domain.billing import (
    BillingAccount,
    BillingPlan,
    BillingScheduleEntry,
    CommissionRecord,
    Invoice,
    InvoiceStatus,
    LineItem,
    PaymentStatus,
)
from openinsure.domain.claim import (
    CauseOfLoss,
    Claim,
    ClaimDocument,
    ClaimStatus,
    Payment,
    Reserve,
    SeverityTier,
)
from openinsure.domain.common import (
    ConfidenceScore,
    DomainEntity,
    Money,
    Percentage,
    Score,
    new_id,
    utc_now,
)
from openinsure.domain.events import (
    AuditGenerated,
    ClaimClosed,
    ClaimPaid,
    ClaimReported,
    ClaimReserved,
    ComplianceAlert,
    DomainEvent,
    EventMetadata,
    PolicyBound,
    PolicyCancelled,
    PolicyEndorsed,
    PolicyRenewed,
    SubmissionQuoted,
    SubmissionReceived,
    SubmissionTriaged,
)
from openinsure.domain.party import (
    Address,
    Contact,
    Party,
    PartyRole,
    PartyType,
    RiskProfile,
)
from openinsure.domain.policy import (
    Coverage,
    Endorsement,
    Policy,
    PolicyDocument,
    PolicyStatus,
)
from openinsure.domain.product import (
    CoverageDefinition,
    ExclusionRule,
    FilingRequirement,
    Product,
    ProductStatus,
    RatingFactor,
)
from openinsure.domain.state_machine import (
    CLAIM_TRANSITIONS,
    POLICY_TRANSITIONS,
    SUBMISSION_TRANSITIONS,
    DomainInvariantError,
    InvalidTransitionError,
    validate_claim_invariants,
    validate_claim_transition,
    validate_policy_invariants,
    validate_policy_transition,
    validate_submission_invariants,
    validate_submission_transition,
)
from openinsure.domain.submission import (
    CyberRiskData,
    Document,
    Submission,
    SubmissionChannel,
    SubmissionStatus,
    TriageResult,
)

__all__ = [
    # state machine
    "CLAIM_TRANSITIONS",
    "POLICY_TRANSITIONS",
    "SUBMISSION_TRANSITIONS",
    # party
    "Address",
    # events
    "AuditGenerated",
    # billing
    "BillingAccount",
    "BillingPlan",
    "BillingScheduleEntry",
    # claim
    "CauseOfLoss",
    "Claim",
    "ClaimClosed",
    "ClaimDocument",
    "ClaimPaid",
    "ClaimReported",
    "ClaimReserved",
    "ClaimStatus",
    "CommissionRecord",
    "ComplianceAlert",
    # common
    "ConfidenceScore",
    "Contact",
    # policy
    "Coverage",
    # product
    "CoverageDefinition",
    # submission
    "CyberRiskData",
    "Document",
    "DomainEntity",
    "DomainEvent",
    "DomainInvariantError",
    "Endorsement",
    "EventMetadata",
    "ExclusionRule",
    "FilingRequirement",
    "InvalidTransitionError",
    "Invoice",
    "InvoiceStatus",
    "LineItem",
    "Money",
    "Party",
    "PartyRole",
    "PartyType",
    "Payment",
    "PaymentStatus",
    "Percentage",
    "Policy",
    "PolicyBound",
    "PolicyCancelled",
    "PolicyDocument",
    "PolicyEndorsed",
    "PolicyRenewed",
    "PolicyStatus",
    "Product",
    "ProductStatus",
    "RatingFactor",
    "Reserve",
    "RiskProfile",
    "Score",
    "SeverityTier",
    "Submission",
    "SubmissionChannel",
    "SubmissionQuoted",
    "SubmissionReceived",
    "SubmissionStatus",
    "SubmissionTriaged",
    "TriageResult",
    "new_id",
    "utc_now",
    "validate_claim_invariants",
    "validate_claim_transition",
    "validate_policy_invariants",
    "validate_policy_transition",
    "validate_submission_invariants",
    "validate_submission_transition",
]
