"""Policy lifecycle management service.

Single source of truth for all policy business logic: binding, endorsement,
renewal, cancellation, and reinstatement.  The agent layer
(``agents/policy_agent.py``) delegates here for business rules; this module
owns validation, premium calculations, and state transitions.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

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
from openinsure.domain.state_machine import validate_policy_transition
from openinsure.domain.submission import Submission
from openinsure.services.policy_transaction_service import record_transaction

logger = structlog.get_logger()


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Pure business-logic helpers (shared by service & agent layers)
# ------------------------------------------------------------------


def validate_bind_requirements(
    quote: dict[str, Any],
    submission: dict[str, Any],
) -> list[str]:
    """Validate that all prerequisites for binding are satisfied."""
    errors: list[str] = []
    if not quote.get("terms"):
        errors.append("Quote has no terms")
    authority = quote.get("authority", {})
    if authority.get("requires_referral") and not authority.get("referral_approved"):
        errors.append("Quote requires referral approval before binding")
    if not submission.get("line_of_business"):
        errors.append("Submission missing line of business")
    return errors


def calculate_endorsement_premium(
    request: dict[str, Any],
    current_premium: Decimal,
) -> Decimal:
    """Calculate the premium change for an endorsement.

    If the request already contains an explicit ``premium_change`` it is
    used directly; otherwise the change is derived from ``change_type``.
    """
    if "premium_change" in request:
        return Decimal(str(request["premium_change"]))

    change_type = request.get("change_type", "")
    increases: dict[str, Decimal] = {
        "increase_limit": Decimal("0.15"),
        "add_coverage": Decimal("0.20"),
    }
    decreases: dict[str, Decimal] = {
        "decrease_limit": Decimal("0.10"),
        "remove_coverage": Decimal("0.15"),
    }

    if change_type in increases:
        return (current_premium * increases[change_type]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if change_type in decreases:
        return -(current_premium * decreases[change_type]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0.00")


def compute_renewal_factor(claims_history: list[dict[str, Any]]) -> Decimal:
    """Compute the renewal premium multiplier from claims history."""
    if not claims_history:
        return Decimal("0.95")  # Claims-free discount

    total_incurred = sum(Decimal(str(c.get("total_incurred", "0"))) for c in claims_history)
    count = len(claims_history)

    if count >= 3 or total_incurred > Decimal("500000"):
        return Decimal("1.35")
    if count >= 2 or total_incurred > Decimal("100000"):
        return Decimal("1.20")
    if total_incurred > Decimal("25000"):
        return Decimal("1.10")
    return Decimal("1.05")


def earned_premium_fraction(
    effective: date,
    expiration: date,
    as_of: date,
) -> Decimal:
    """Return the fraction of premium earned as of *as_of*."""
    total_days = (expiration - effective).days
    if total_days <= 0:
        return Decimal("1.0")
    elapsed_days = min(max((as_of - effective).days, 0), total_days)
    return (Decimal(str(elapsed_days)) / Decimal(str(total_days))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_earned_unearned(
    total_premium: Decimal,
    effective_date: str,
    expiration_date: str,
    cancel_date: str,
) -> tuple[Decimal, Decimal]:
    """Pro-rata earned/unearned premium split from ISO date strings."""
    eff = date.fromisoformat(str(effective_date))
    exp = date.fromisoformat(str(expiration_date))
    cancel = date.fromisoformat(str(cancel_date))

    total_days = max((exp - eff).days, 1)
    elapsed_days = max((cancel - eff).days, 0)
    frac = Decimal(str(elapsed_days)) / Decimal(str(total_days))

    earned = (total_premium * frac).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    unearned = total_premium - earned
    return earned, unearned


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _generate_policy_number() -> str:
    """Generate a unique policy number."""
    uid = new_id()
    return f"POL-{str(uid)[:8].upper()}"


def _generate_endorsement_number(policy: Policy) -> str:
    """Generate an endorsement number based on policy and sequence."""
    seq = len(policy.endorsements) + 1
    return f"{policy.policy_number}-END-{seq:03d}"


# ------------------------------------------------------------------
# Service class
# ------------------------------------------------------------------


class PolicyLifecycleService:
    """Service managing the full policy lifecycle.

    All state-changing operations enforce domain state-machine transitions
    via ``validate_policy_transition`` from ``domain.state_machine``.
    """

    async def bind_policy(self, request: BindRequest) -> PolicyLifecycleResult:
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

        # Record new_business transaction
        await record_transaction(
            policy_id=str(policy.id),
            transaction_type="new_business",
            effective_date=request.effective_date,
            expiration_date=request.expiration_date,
            premium_change=float(request.total_premium),
            description=f"New business: {policy_number}",
            coverages_snapshot=[c.model_dump(mode="json") for c in request.coverages],
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

    async def endorse_policy(
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
        fraction = earned_premium_fraction(policy.effective_date, policy.expiration_date, date.today())
        policy.earned_premium = (policy.total_premium * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        policy.unearned_premium = policy.total_premium - policy.earned_premium
        policy.updated_at = datetime.now(UTC)

        # Record endorsement transaction with coverage snapshot
        await record_transaction(
            policy_id=str(policy.id),
            transaction_type="endorsement",
            effective_date=request.effective_date,
            premium_change=float(request.premium_change),
            description=request.description,
            coverages_snapshot=[c.model_dump(mode="json") for c in policy.coverages],
        )

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

    async def renew_policy(self, policy: Policy) -> PolicyLifecycleResult:
        """Generate a renewal policy from an existing policy."""
        if policy.status not in (PolicyStatus.active, PolicyStatus.expired):
            msg = f"Cannot renew policy in {policy.status} status"
            raise ValueError(msg)

        renewal_number = _generate_policy_number()
        term_days = (policy.expiration_date - policy.effective_date).days

        new_effective = policy.expiration_date
        new_expiration = policy.expiration_date + timedelta(days=term_days)

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

        # Record renewal transaction
        await record_transaction(
            policy_id=str(renewal.id),
            transaction_type="renewal",
            effective_date=new_effective,
            expiration_date=new_expiration,
            premium_change=float(renewal.total_premium),
            description=f"Renewal of {policy.policy_number}",
            coverages_snapshot=[c.model_dump(mode="json") for c in policy.coverages],
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

    async def cancel_policy(
        self,
        policy: Policy,
        request: CancellationRequest,
    ) -> PolicyLifecycleResult:
        """Cancel a policy and calculate earned/unearned premium split."""
        validate_policy_transition(policy.status.value, "cancelled")

        fraction = earned_premium_fraction(policy.effective_date, policy.expiration_date, request.effective_date)
        earned = (policy.total_premium * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        unearned = policy.total_premium - earned

        policy.status = PolicyStatus.cancelled
        policy.earned_premium = earned
        policy.unearned_premium = unearned
        policy.cancelled_at = datetime.now(UTC)
        policy.cancel_reason = request.reason
        policy.updated_at = datetime.now(UTC)

        # Record cancellation transaction
        await record_transaction(
            policy_id=str(policy.id),
            transaction_type="cancellation",
            effective_date=request.effective_date,
            premium_change=-float(unearned),
            description=request.reason,
        )

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

    async def reinstate_policy(self, policy: Policy) -> PolicyLifecycleResult:
        """Reinstate a previously cancelled policy."""
        validate_policy_transition(policy.status.value, "reinstated")

        policy.status = PolicyStatus.reinstated
        policy.updated_at = datetime.now(UTC)

        # Recalculate earned/unearned as of today
        fraction = earned_premium_fraction(policy.effective_date, policy.expiration_date, date.today())
        policy.earned_premium = (policy.total_premium * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        policy.unearned_premium = policy.total_premium - policy.earned_premium

        # Record reinstatement transaction
        await record_transaction(
            policy_id=str(policy.id),
            transaction_type="reinstatement",
            effective_date=date.today(),
            premium_change=float(policy.unearned_premium),
            description=f"Reinstatement of {policy.policy_number}",
        )

        logger.info(
            "policy.reinstated",
            policy_number=policy.policy_number,
        )

        return PolicyLifecycleResult(
            policy=policy,
            events=[],
            message=f"Policy {policy.policy_number} reinstated",
        )
