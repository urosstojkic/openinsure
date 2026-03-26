"""Claims processing service.

Handles the full claims lifecycle from first notice of loss through
investigation, reserving, payment, and closure.
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from openinsure.domain.claim import (
    CauseOfLoss,
    Claim,
    ClaimStatus,
    Payment,
    Reserve,
    SeverityTier,
)
from openinsure.domain.common import Money, new_id
from openinsure.domain.events import (
    ClaimClosed,
    ClaimPaid,
    ClaimReported,
    ClaimReserved,
    DomainEvent,
)
from openinsure.domain.limits import PLATFORM_LIMITS
from openinsure.domain.policy import Policy, PolicyStatus

logger = structlog.get_logger()


class FNOLRequest(BaseModel):
    """First notice of loss intake request."""

    policy_id: UUID
    loss_date: date
    report_date: date = Field(default_factory=date.today)
    loss_type: str
    cause_of_loss: CauseOfLoss
    description: str
    severity: SeverityTier = SeverityTier.moderate
    claimant_ids: list[UUID] = Field(default_factory=list)


class CoverageVerificationResult(BaseModel):
    """Result of coverage verification for a claim."""

    is_covered: bool
    policy_active: bool
    loss_within_period: bool
    exclusions_apply: bool
    reasons: list[str] = Field(default_factory=list)


class ReserveRequest(BaseModel):
    """Request to set reserves on a claim."""

    reserve_type: str = "indemnity"
    amount: Money
    set_by: str = "system"
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class PaymentRequest(BaseModel):
    """Request to process a claim payment."""

    amount: Money
    payee_id: UUID
    payment_type: str = "indemnity"


class ClaimsProcessingResult(BaseModel):
    """Result of a claims processing operation."""

    claim: Claim
    events: list[DomainEvent] = Field(default_factory=list)
    message: str


def _generate_claim_number() -> str:
    """Generate a unique claim number."""
    uid = new_id()
    return f"CLM-{str(uid)[:8].upper()}"


# Reserve recommendations by severity tier — sourced from centralized limits
RESERVE_GUIDELINES: dict[SeverityTier, tuple[Decimal, Decimal]] = {
    SeverityTier.simple: PLATFORM_LIMITS.reserves.for_tier("simple"),
    SeverityTier.moderate: PLATFORM_LIMITS.reserves.for_tier("moderate"),
    SeverityTier.complex: PLATFORM_LIMITS.reserves.for_tier("complex"),
    SeverityTier.catastrophe: PLATFORM_LIMITS.reserves.for_tier("catastrophe"),
}


class ClaimsProcessingService:
    """Service managing the full claims lifecycle."""

    def intake_fnol(self, request: FNOLRequest) -> ClaimsProcessingResult:
        """Accept a first notice of loss and create a claim record."""
        claim_number = _generate_claim_number()

        claim = Claim(
            claim_number=claim_number,
            status=ClaimStatus.fnol,
            policy_id=request.policy_id,
            loss_date=request.loss_date,
            report_date=request.report_date,
            loss_type=request.loss_type,
            cause_of_loss=request.cause_of_loss,
            description=request.description,
            severity=request.severity,
            claimant_ids=request.claimant_ids,
        )

        event = ClaimReported.create(
            claim_id=claim.id,
            payload={
                "claim_number": claim_number,
                "cause_of_loss": request.cause_of_loss.value,
                "severity": request.severity.value,
            },
        )

        logger.info(
            "claim.fnol_received",
            claim_number=claim_number,
            cause=request.cause_of_loss.value,
            severity=request.severity.value,
        )

        return ClaimsProcessingResult(
            claim=claim,
            events=[event],
            message=f"Claim {claim_number} created from FNOL",
        )

    def verify_coverage(
        self,
        claim: Claim,
        policy: Policy,
    ) -> CoverageVerificationResult:
        """Check that the policy covers the reported loss."""
        reasons: list[str] = []

        policy_active = policy.status == PolicyStatus.active
        if not policy_active:
            reasons.append(f"Policy is in {policy.status} status")

        loss_within_period = policy.effective_date <= claim.loss_date <= policy.expiration_date
        if not loss_within_period:
            reasons.append(
                f"Loss date {claim.loss_date} outside policy period {policy.effective_date} to {policy.expiration_date}"
            )

        # Simple exclusion check — cyber-specific causes covered by default
        exclusions_apply = False
        if claim.cause_of_loss == CauseOfLoss.other:
            exclusions_apply = True
            reasons.append("Cause of loss 'other' may not be covered")

        is_covered = policy_active and loss_within_period and not exclusions_apply

        if is_covered:
            reasons.append("Coverage verified — claim is covered")

        logger.info(
            "claim.coverage_verified",
            claim_number=claim.claim_number,
            is_covered=is_covered,
        )

        return CoverageVerificationResult(
            is_covered=is_covered,
            policy_active=policy_active,
            loss_within_period=loss_within_period,
            exclusions_apply=exclusions_apply,
            reasons=reasons,
        )

    def set_reserves(
        self,
        claim: Claim,
        request: ReserveRequest | None = None,
    ) -> ClaimsProcessingResult:
        """Set or update reserves on a claim based on severity."""
        if request is None:
            low, high = RESERVE_GUIDELINES.get(claim.severity, (Decimal("25000"), Decimal("100000")))
            amount = ((low + high) / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            request = ReserveRequest(amount=amount, set_by="system", confidence=0.7)

        reserve = Reserve(
            reserve_type=request.reserve_type,
            amount=request.amount,
            set_date=datetime.now(UTC),
            set_by=request.set_by,
            confidence=request.confidence,
        )

        claim.reserves.append(reserve)
        claim.status = ClaimStatus.reserved
        claim.updated_at = datetime.now(UTC)

        event = ClaimReserved.create(
            claim_id=claim.id,
            payload={
                "claim_number": claim.claim_number,
                "reserve_type": request.reserve_type,
                "amount": str(request.amount),
            },
        )

        logger.info(
            "claim.reserves_set",
            claim_number=claim.claim_number,
            amount=str(request.amount),
        )

        return ClaimsProcessingResult(
            claim=claim,
            events=[event],
            message=f"Reserve of ${request.amount:,.2f} set on {claim.claim_number}",
        )

    def process_payment(
        self,
        claim: Claim,
        request: PaymentRequest,
    ) -> ClaimsProcessingResult:
        """Record a payment against a claim."""
        if claim.status in (ClaimStatus.closed, ClaimStatus.denied):
            msg = f"Cannot process payment on claim in {claim.status} status"
            raise ValueError(msg)

        payment = Payment(
            amount=request.amount,
            payee_id=request.payee_id,
            payment_date=datetime.now(UTC),
            payment_type=request.payment_type,
        )

        claim.payments.append(payment)
        claim.status = ClaimStatus.settling
        claim.updated_at = datetime.now(UTC)

        event = ClaimPaid.create(
            claim_id=claim.id,
            payload={
                "claim_number": claim.claim_number,
                "amount": str(request.amount),
                "payment_type": request.payment_type,
            },
        )

        logger.info(
            "claim.payment_processed",
            claim_number=claim.claim_number,
            amount=str(request.amount),
        )

        return ClaimsProcessingResult(
            claim=claim,
            events=[event],
            message=f"Payment of ${request.amount:,.2f} processed on {claim.claim_number}",
        )

    def close_claim(
        self,
        claim: Claim,
        reason: str,
    ) -> ClaimsProcessingResult:
        """Close a claim with a final disposition."""
        if claim.status == ClaimStatus.closed:
            msg = "Claim is already closed"
            raise ValueError(msg)

        claim.status = ClaimStatus.closed
        claim.closed_at = datetime.now(UTC)
        claim.close_reason = reason
        claim.updated_at = datetime.now(UTC)

        event = ClaimClosed.create(
            claim_id=claim.id,
            payload={
                "claim_number": claim.claim_number,
                "reason": reason,
                "total_incurred": str(claim.total_incurred),
            },
        )

        logger.info(
            "claim.closed",
            claim_number=claim.claim_number,
            total_incurred=str(claim.total_incurred),
        )

        return ClaimsProcessingResult(
            claim=claim,
            events=[event],
            message=f"Claim {claim.claim_number} closed — {reason}",
        )
