"""Domain-specific exceptions for OpenInsure.

These exceptions represent business rule violations at the domain layer.
They are mapped to HTTP status codes by exception handlers in ``main.py``.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all domain-level errors."""

    status_code: int = 500
    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


# Backward-compatible alias
DomainException = DomainError


class SubmissionNotFoundError(DomainException):
    """Raised when a submission cannot be found."""

    status_code = 404
    code = "SUBMISSION_NOT_FOUND"

    def __init__(self, submission_id: str) -> None:
        super().__init__(
            f"Submission '{submission_id}' not found",
            details={"resource_type": "submission", "resource_id": submission_id},
        )


class PolicyNotFoundError(DomainException):
    """Raised when a policy cannot be found."""

    status_code = 404
    code = "POLICY_NOT_FOUND"

    def __init__(self, policy_id: str) -> None:
        super().__init__(
            f"Policy '{policy_id}' not found",
            details={"resource_type": "policy", "resource_id": policy_id},
        )


class ClaimNotFoundError(DomainException):
    """Raised when a claim cannot be found."""

    status_code = 404
    code = "CLAIM_NOT_FOUND"

    def __init__(self, claim_id: str) -> None:
        super().__init__(
            f"Claim '{claim_id}' not found",
            details={"resource_type": "claim", "resource_id": claim_id},
        )


class InvalidStateTransitionError(DomainException):
    """Raised when an entity cannot transition to the requested state."""

    status_code = 409
    code = "INVALID_STATE_TRANSITION"

    def __init__(self, entity_type: str, current: str, target: str, reason: str = "") -> None:
        msg = f"{entity_type} cannot transition from '{current}' to '{target}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"entity_type": entity_type, "current": current, "target": target})
        self.entity_type = entity_type
        self.current_state = current
        self.target_state = target


class AuthorityExceededError(DomainException):
    """Raised when an action exceeds the user's delegated authority."""

    status_code = 403
    code = "AUTHORITY_EXCEEDED"

    def __init__(self, action: str, limit: str = "") -> None:
        msg = f"Authority exceeded for action '{action}'"
        if limit:
            msg += f": limit is {limit}"
        super().__init__(msg, details={"action": action, "limit": limit})


class AppetiteDeclinedError(DomainException):
    """Raised when a submission does not match the carrier's risk appetite."""

    status_code = 422
    code = "APPETITE_DECLINED"

    def __init__(self, reason: str, *, lob: str = "") -> None:
        msg = f"Submission declined: {reason}"
        super().__init__(msg, details={"reason": reason, "lob": lob})


class ValidationError(DomainException):
    """Raised when input validation fails at the domain level."""

    status_code = 422
    code = "VALIDATION_ERROR"

    def __init__(self, message: str, *, field: str = "") -> None:
        super().__init__(message, details={"field": field})
