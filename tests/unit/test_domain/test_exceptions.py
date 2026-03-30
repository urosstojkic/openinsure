"""Tests for domain exception hierarchy.

Verifies that all domain exceptions have correct status codes, error codes,
and message formatting.
"""

from __future__ import annotations

import pytest

from openinsure.domain.exceptions import (
    AppetiteDeclinedError,
    AuthorityExceededError,
    ClaimNotFoundError,
    DomainError,
    DomainException,
    InvalidStateTransitionError,
    PolicyNotFoundError,
    SubmissionNotFoundError,
    ValidationError,
)


class TestDomainExceptions:
    """Test the domain exception hierarchy."""

    def test_base_domain_exception(self):
        exc = DomainError("something went wrong")
        assert str(exc) == "something went wrong"
        assert exc.status_code == 500
        assert exc.code == "DOMAIN_ERROR"
        assert exc.details == {}

    def test_domain_exception_alias(self):
        """DomainException is a backward-compatible alias for DomainError."""
        assert DomainException is DomainError

    def test_submission_not_found(self):
        exc = SubmissionNotFoundError("sub-123")
        assert "sub-123" in str(exc)
        assert exc.status_code == 404
        assert exc.code == "SUBMISSION_NOT_FOUND"
        assert exc.details["resource_type"] == "submission"
        assert exc.details["resource_id"] == "sub-123"

    def test_policy_not_found(self):
        exc = PolicyNotFoundError("pol-456")
        assert "pol-456" in str(exc)
        assert exc.status_code == 404
        assert exc.code == "POLICY_NOT_FOUND"

    def test_claim_not_found(self):
        exc = ClaimNotFoundError("clm-789")
        assert "clm-789" in str(exc)
        assert exc.status_code == 404
        assert exc.code == "CLAIM_NOT_FOUND"

    def test_invalid_state_transition(self):
        exc = InvalidStateTransitionError("Policy", "active", "expired", "term not reached")
        assert "active" in str(exc)
        assert "expired" in str(exc)
        assert "term not reached" in str(exc)
        assert exc.status_code == 409
        assert exc.code == "INVALID_STATE_TRANSITION"
        assert exc.entity_type == "Policy"
        assert exc.current_state == "active"
        assert exc.target_state == "expired"

    def test_invalid_state_transition_no_reason(self):
        exc = InvalidStateTransitionError("Submission", "received", "bound")
        assert "received" in str(exc)
        assert "bound" in str(exc)

    def test_authority_exceeded(self):
        exc = AuthorityExceededError("bind", "$500,000")
        assert "bind" in str(exc)
        assert "$500,000" in str(exc)
        assert exc.status_code == 403
        assert exc.code == "AUTHORITY_EXCEEDED"

    def test_appetite_declined(self):
        exc = AppetiteDeclinedError("revenue outside appetite", lob="cyber")
        assert "revenue outside appetite" in str(exc)
        assert exc.status_code == 422
        assert exc.code == "APPETITE_DECLINED"
        assert exc.details["lob"] == "cyber"

    def test_validation_error(self):
        exc = ValidationError("Invalid email format", field="email")
        assert "Invalid email format" in str(exc)
        assert exc.status_code == 422
        assert exc.code == "VALIDATION_ERROR"
        assert exc.details["field"] == "email"

    def test_all_exceptions_inherit_from_domain_exception(self):
        """Ensure all domain exceptions inherit from DomainError."""
        exceptions = [
            SubmissionNotFoundError("x"),
            PolicyNotFoundError("x"),
            ClaimNotFoundError("x"),
            InvalidStateTransitionError("X", "a", "b"),
            AuthorityExceededError("x"),
            AppetiteDeclinedError("x"),
            ValidationError("x"),
        ]
        for exc in exceptions:
            assert isinstance(exc, DomainError)
            assert isinstance(exc, Exception)
