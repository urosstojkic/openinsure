"""Tests for domain state machine enforcement and business invariants."""

from __future__ import annotations

import pytest

from openinsure.domain.state_machine import (
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

# ---------------------------------------------------------------------------
# Submission transition tests
# ---------------------------------------------------------------------------


class TestSubmissionTransitions:
    """Verify every allowed and disallowed submission state transition."""

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("received", "triaging"),
            ("received", "declined"),
            ("triaging", "underwriting"),
            ("triaging", "declined"),
            ("underwriting", "quoted"),
            ("underwriting", "declined"),
            ("underwriting", "referred"),
            ("referred", "quoted"),
            ("referred", "declined"),
            ("quoted", "bound"),
            ("quoted", "declined"),
            ("quoted", "expired"),
        ],
    )
    def test_valid_transitions(self, current: str, target: str) -> None:
        validate_submission_transition(current, target)  # should not raise

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("received", "bound"),
            ("received", "quoted"),
            ("triaging", "bound"),
            ("bound", "received"),
            ("declined", "received"),
            ("expired", "received"),
            ("quoted", "triaging"),
            ("underwriting", "received"),
        ],
    )
    def test_invalid_transitions(self, current: str, target: str) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_submission_transition(current, target)
        assert exc_info.value.entity_type == "Submission"
        assert exc_info.value.current_state == current
        assert exc_info.value.target_state == target

    def test_unknown_state_raises(self) -> None:
        with pytest.raises(InvalidTransitionError):
            validate_submission_transition("nonexistent", "triaging")

    def test_terminal_states_have_no_transitions(self) -> None:
        for state in ("bound", "declined", "expired"):
            assert SUBMISSION_TRANSITIONS[state] == set()


# ---------------------------------------------------------------------------
# Policy transition tests
# ---------------------------------------------------------------------------


class TestPolicyTransitions:
    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("pending", "active"),
            ("active", "cancelled"),
            ("active", "expired"),
            ("active", "suspended"),
            ("suspended", "active"),
            ("suspended", "cancelled"),
        ],
    )
    def test_valid_transitions(self, current: str, target: str) -> None:
        validate_policy_transition(current, target)

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("pending", "cancelled"),
            ("pending", "expired"),
            ("active", "pending"),
            ("cancelled", "active"),
            ("expired", "active"),
            ("suspended", "expired"),
        ],
    )
    def test_invalid_transitions(self, current: str, target: str) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_policy_transition(current, target)
        assert exc_info.value.entity_type == "Policy"

    def test_terminal_states(self) -> None:
        for state in ("cancelled", "expired"):
            assert POLICY_TRANSITIONS[state] == set()


# ---------------------------------------------------------------------------
# Claim transition tests
# ---------------------------------------------------------------------------


class TestClaimTransitions:
    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("fnol", "investigating"),
            ("investigating", "reserved"),
            ("investigating", "denied"),
            ("reserved", "settling"),
            ("reserved", "investigating"),
            ("reserved", "denied"),
            ("settling", "closed"),
            ("closed", "reopened"),
            ("reopened", "investigating"),
            ("denied", "reopened"),
        ],
    )
    def test_valid_transitions(self, current: str, target: str) -> None:
        validate_claim_transition(current, target)

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("fnol", "closed"),
            ("fnol", "denied"),
            ("investigating", "closed"),
            ("settling", "investigating"),
            ("closed", "settling"),
            ("denied", "settling"),
        ],
    )
    def test_invalid_transitions(self, current: str, target: str) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_claim_transition(current, target)
        assert exc_info.value.entity_type == "Claim"


# ---------------------------------------------------------------------------
# Submission invariants
# ---------------------------------------------------------------------------


class TestSubmissionInvariants:
    def test_quoted_without_triage_result(self) -> None:
        with pytest.raises(DomainInvariantError, match="triage_result"):
            validate_submission_invariants({"status": "quoted", "triage_result": None})

    def test_quoted_with_triage_result_ok(self) -> None:
        validate_submission_invariants({"status": "quoted", "triage_result": {"score": 80}})

    def test_bound_without_quoted_premium(self) -> None:
        with pytest.raises(DomainInvariantError, match="quoted_premium"):
            validate_submission_invariants({"status": "bound", "quoted_premium": None})

    def test_bound_with_quoted_premium_ok(self) -> None:
        validate_submission_invariants({"status": "bound", "quoted_premium": 1500.0, "triage_result": {"score": 80}})

    def test_received_no_invariants(self) -> None:
        validate_submission_invariants({"status": "received"})


# ---------------------------------------------------------------------------
# Policy invariants
# ---------------------------------------------------------------------------


class TestPolicyInvariants:
    def test_effective_after_expiration(self) -> None:
        with pytest.raises(DomainInvariantError, match="effective_date must be before"):
            validate_policy_invariants(
                {"effective_date": "2025-12-01", "expiration_date": "2025-01-01", "premium": 100}
            )

    def test_effective_equals_expiration(self) -> None:
        with pytest.raises(DomainInvariantError, match="effective_date must be before"):
            validate_policy_invariants(
                {"effective_date": "2025-06-01", "expiration_date": "2025-06-01", "premium": 100}
            )

    def test_valid_dates_ok(self) -> None:
        validate_policy_invariants({"effective_date": "2025-01-01", "expiration_date": "2025-12-31", "premium": 100})

    def test_negative_premium(self) -> None:
        with pytest.raises(DomainInvariantError, match="premium cannot be negative"):
            validate_policy_invariants({"premium": -50.0})

    def test_zero_premium_ok(self) -> None:
        validate_policy_invariants({"premium": 0})


# ---------------------------------------------------------------------------
# Claim invariants
# ---------------------------------------------------------------------------


class TestClaimInvariants:
    def test_negative_reserve(self) -> None:
        with pytest.raises(DomainInvariantError, match="reserve amount cannot be negative"):
            validate_claim_invariants({"reserves": [{"amount": -100}]})

    def test_valid_reserves_ok(self) -> None:
        validate_claim_invariants({"reserves": [{"amount": 500}, {"amount": 0}]})

    def test_empty_reserves_ok(self) -> None:
        validate_claim_invariants({"reserves": []})

    def test_no_reserves_key_ok(self) -> None:
        validate_claim_invariants({})


# ---------------------------------------------------------------------------
# Error message formatting
# ---------------------------------------------------------------------------


class TestErrorMessages:
    def test_invalid_transition_message(self) -> None:
        err = InvalidTransitionError("Submission", "bound", "received", reason="terminal state")
        assert "Submission cannot transition from 'bound' to 'received'" in str(err)
        assert "terminal state" in str(err)

    def test_domain_invariant_message(self) -> None:
        err = DomainInvariantError("Policy", "dates invalid", details="eff > exp")
        assert "Policy invariant violated: dates invalid" in str(err)
        assert "eff > exp" in str(err)

    def test_invalid_transition_no_reason(self) -> None:
        err = InvalidTransitionError("Claim", "fnol", "closed")
        assert "Claim cannot transition from 'fnol' to 'closed'" in str(err)
        assert ": " not in str(err).split("'closed'")[-1]

    def test_domain_invariant_no_details(self) -> None:
        err = DomainInvariantError("Claim", "bad state")
        assert "Claim invariant violated: bad state" in str(err)
        assert "(" not in str(err)
