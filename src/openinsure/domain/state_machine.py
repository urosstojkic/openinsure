"""Domain state machine enforcement for insurance entities.

Ensures valid state transitions and business invariants are checked
at the domain layer, not just the API layer.
"""

from typing import Any


class InvalidTransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, entity_type: str, current: str, target: str, reason: str = ""):
        msg = f"{entity_type} cannot transition from '{current}' to '{target}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.entity_type = entity_type
        self.current_state = current
        self.target_state = target


class DomainInvariantError(ValueError):
    """Raised when a domain invariant is violated."""

    def __init__(self, entity_type: str, invariant: str, details: str = ""):
        msg = f"{entity_type} invariant violated: {invariant}"
        if details:
            msg += f" ({details})"
        super().__init__(msg)


# Valid state transitions
SUBMISSION_TRANSITIONS: dict[str, set[str]] = {
    "received": {"triaging", "underwriting", "declined"},
    "triaging": {"underwriting", "declined"},
    "underwriting": {"quoted", "declined"},
    "quoted": {"bound", "declined", "expired"},
    "bound": set(),  # terminal
    "declined": set(),  # terminal
    "expired": set(),  # terminal
}

POLICY_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"active"},
    "active": {"cancelled", "expired", "suspended"},
    "suspended": {"active", "cancelled"},
    "cancelled": set(),
    "expired": set(),
}

CLAIM_TRANSITIONS: dict[str, set[str]] = {
    "reported": {"investigating", "reserved"},
    "fnol": {"investigating", "reserved"},
    "investigating": {"reserved", "denied"},
    "reserved": {"settling", "investigating", "denied"},
    "settling": {"closed"},
    "closed": {"reopened"},
    "reopened": {"investigating"},
    "denied": {"reopened"},
}


def validate_submission_transition(current: str, target: str) -> None:
    """Validate a submission state transition."""
    allowed = SUBMISSION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError("Submission", current, target)


def validate_policy_transition(current: str, target: str) -> None:
    """Validate a policy state transition."""
    allowed = POLICY_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError("Policy", current, target)


def validate_claim_transition(current: str, target: str) -> None:
    """Validate a claim state transition."""
    allowed = CLAIM_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError("Claim", current, target)


def validate_submission_invariants(submission: dict[str, Any]) -> None:
    """Check business invariants on a submission."""
    status = submission.get("status", "")

    # Cannot quote without triage result
    if status == "quoted" and not submission.get("triage_result"):
        raise DomainInvariantError("Submission", "cannot quote without triage_result")

    # Cannot bind without quoted premium
    if status == "bound" and not submission.get("quoted_premium"):
        raise DomainInvariantError("Submission", "cannot bind without quoted_premium")


def validate_policy_invariants(policy: dict[str, Any]) -> None:
    """Check business invariants on a policy."""
    eff = policy.get("effective_date", "")
    exp = policy.get("expiration_date", "")
    if eff and exp and str(eff) >= str(exp):
        raise DomainInvariantError(
            "Policy",
            "effective_date must be before expiration_date",
            f"effective={eff}, expiration={exp}",
        )

    premium = policy.get("total_premium", policy.get("premium", 0))
    if premium is not None and float(premium) < 0:
        raise DomainInvariantError("Policy", "premium cannot be negative")


def validate_claim_invariants(claim: dict[str, Any]) -> None:
    """Check business invariants on a claim."""
    reserves = claim.get("reserves", [])
    if isinstance(reserves, list):
        for r in reserves:
            if isinstance(r, dict) and float(r.get("amount", 0)) < 0:
                raise DomainInvariantError("Claim", "reserve amount cannot be negative")
