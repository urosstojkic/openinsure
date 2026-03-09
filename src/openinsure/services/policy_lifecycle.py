"""Policy lifecycle management service.

Handles the full lifecycle of insurance policies: binding, endorsement,
renewal, and cancellation with earned/unearned premium calculations.
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

import structlog
from pydantic import BaseModel, Field

from openinsure.domain.common import Money, new_id
from openinsure.domain.events import (
    DomainEvent,
    PolicyBound,
    PolicyCancelled,
    PolicyEndorsed,
    PolicyRenewed,
)
from openinsure.domain.policy import (
    Coverage,
    Endorsement,
    Policy,
    PolicyStatus,
)
from openinsure.domain.submission import Submission

logger = structlog.get_logger()


class BindRequest(BaseModel):
    """Request to bind a policy from a submission."""

    submission: Submission
    coverages: list[Coverage]
    effective_date: date
    expiration_date: date
    total_premium: Money


class EndorsementRequest(BaseModel):
    """Request for a mid-term policy endorsement."""

    description: str
    effective_date: date
    premium_change: Decimal
    coverages_modified: list[str] = Field(default_factory=list)


class CancellationRequest(BaseModel):
    """Request to cancel a policy."""

    reason: str
    effective_date: date


class PolicyLifecycleResult(BaseModel):
    """Result of a policy lifecycle operation."""

    policy: Policy
    events: list[DomainEvent] = Field(default_factory=list)
    message: str


def _generate_policy_number() -> str:
    """Generate a unique policy number."""
    uid = new_id()
    return f"POL-{str(uid)[:8].upper()}"


def _generate_endorsement_number(policy: Policy) -> str:
    """Generate an endorsement number based on policy and sequence."""
    seq = len(policy.endorsements) + 1
    return f"{policy.policy_number}-END-{seq:03d}"


def _earned_premium_fraction(
    effective: date,
    expiration: date,
    as_of: date,
) -> Decimal:
    """Calculate the earned fraction of a policy term."""
    total_days = (expiration - effective).days
    if total_days <= 0:
        return Decimal("1.0")
    elapsed_days = min(max((as_of - effective).days, 0), total_days)
    return (Decimal(str(elapsed_days)) / Decimal(str(total_days))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class PolicyLifecycleService:
    """Service managing the full policy lifecycle."""

    def bind_policy(self, request: BindRequest) -> PolicyLifecycleResult:
        """Create a new policy from a submission and bind it."""
        policy_number = _generate_policy_number()

        written_premium = request.total_premium
        earned = Decimal("0.00")
        unearned = written_premium

        policy = Policy(
            policy_number=policy_number,
            status=PolicyStatus.active,
            product_id=new_id(),
            submission_id=request.submission.id,
            insured_id=request.submission.applicant,
            broker_id=request.submission.broker,
            effective_date=request.effective_date,
            expiration_date=request.expiration_date,
            coverages=request.coverages,
            total_premium=request.total_premium,
            written_premium=written_premium,
            earned_premium=earned,
            unearned_premium=unearned,
            bound_at=datetime.now(UTC),
        )

        event = PolicyBound.create(
            policy_id=policy.id,
            payload={
                "policy_number": policy_number,
                "premium": str(request.total_premium),
                "submission_id": str(request.submission.id),
            },
        )

        logger.info(
            "policy.bound",
            policy_number=policy_number,
            premium=str(request.total_premium),
        )

        return PolicyLifecycleResult(
            policy=policy,
            events=[event],
            message=f"Policy {policy_number} bound successfully",
        )

    def endorse_policy(
        self,
        policy: Policy,
        request: EndorsementRequest,
    ) -> PolicyLifecycleResult:
        """Process a mid-term endorsement on an existing policy."""
        if policy.status != PolicyStatus.active:
            msg = f"Cannot endorse policy in {policy.status} status"
            raise ValueError(msg)

        endorsement_number = _generate_endorsement_number(policy)

        endorsement = Endorsement(
            endorsement_number=endorsement_number,
            effective_date=request.effective_date,
            description=request.description,
            premium_change=request.premium_change,
            coverages_modified=request.coverages_modified,
        )

        policy.endorsements.append(endorsement)

        # Recalculate total premium
        policy.total_premium += request.premium_change
        policy.written_premium += request.premium_change

        # Recalculate earned/unearned as of now
        fraction = _earned_premium_fraction(policy.effective_date, policy.expiration_date, date.today())
        policy.earned_premium = (policy.total_premium * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        policy.unearned_premium = policy.total_premium - policy.earned_premium
        policy.updated_at = datetime.now(UTC)

        event = PolicyEndorsed.create(
            policy_id=policy.id,
            payload={
                "endorsement_number": endorsement_number,
                "premium_change": str(request.premium_change),
                "description": request.description,
            },
        )

        logger.info(
            "policy.endorsed",
            policy_number=policy.policy_number,
            endorsement=endorsement_number,
            premium_change=str(request.premium_change),
        )

        return PolicyLifecycleResult(
            policy=policy,
            events=[event],
            message=f"Endorsement {endorsement_number} applied to {policy.policy_number}",
        )

    def renew_policy(self, policy: Policy) -> PolicyLifecycleResult:
        """Generate a renewal policy from an existing policy."""
        if policy.status not in (PolicyStatus.active, PolicyStatus.expired):
            msg = f"Cannot renew policy in {policy.status} status"
            raise ValueError(msg)

        renewal_number = _generate_policy_number()
        term_days = (policy.expiration_date - policy.effective_date).days

        new_effective = policy.expiration_date
        new_expiration = policy.expiration_date + __import__("datetime").timedelta(days=term_days)

        renewal = Policy(
            policy_number=renewal_number,
            status=PolicyStatus.active,
            product_id=policy.product_id,
            submission_id=policy.submission_id,
            insured_id=policy.insured_id,
            broker_id=policy.broker_id,
            effective_date=new_effective,
            expiration_date=new_expiration,
            coverages=policy.coverages.copy(),
            total_premium=policy.total_premium,
            written_premium=policy.total_premium,
            earned_premium=Decimal("0.00"),
            unearned_premium=policy.total_premium,
            bound_at=datetime.now(UTC),
        )

        event = PolicyRenewed.create(
            policy_id=renewal.id,
            payload={
                "renewal_number": renewal_number,
                "prior_policy": policy.policy_number,
                "premium": str(renewal.total_premium),
            },
        )

        logger.info(
            "policy.renewed",
            prior_policy=policy.policy_number,
            renewal_number=renewal_number,
        )

        return PolicyLifecycleResult(
            policy=renewal,
            events=[event],
            message=f"Renewal {renewal_number} generated from {policy.policy_number}",
        )

    def cancel_policy(
        self,
        policy: Policy,
        request: CancellationRequest,
    ) -> PolicyLifecycleResult:
        """Cancel a policy and calculate earned/unearned premium split."""
        if policy.status != PolicyStatus.active:
            msg = f"Cannot cancel policy in {policy.status} status"
            raise ValueError(msg)

        fraction = _earned_premium_fraction(policy.effective_date, policy.expiration_date, request.effective_date)
        earned = (policy.total_premium * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        unearned = policy.total_premium - earned

        policy.status = PolicyStatus.cancelled
        policy.earned_premium = earned
        policy.unearned_premium = unearned
        policy.cancelled_at = datetime.now(UTC)
        policy.cancel_reason = request.reason
        policy.updated_at = datetime.now(UTC)

        event = PolicyCancelled.create(
            policy_id=policy.id,
            payload={
                "reason": request.reason,
                "earned_premium": str(earned),
                "unearned_premium": str(unearned),
            },
        )

        logger.info(
            "policy.cancelled",
            policy_number=policy.policy_number,
            earned=str(earned),
            unearned=str(unearned),
        )

        return PolicyLifecycleResult(
            policy=policy,
            events=[event],
            message=f"Policy {policy.policy_number} cancelled — unearned premium: ${unearned:,.2f}",
        )
