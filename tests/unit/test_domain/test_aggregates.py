"""Tests for aggregate root pattern (DDD aggregate boundaries).

Covers:
- SubmissionAggregate state transitions and event emission
- PolicyAggregate state transitions and event emission
- ClaimAggregate state transitions and event emission
- Invalid transition rejection
- Domain invariant enforcement
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from openinsure.domain.aggregates.claim import ClaimAggregate, ClaimDenied
from openinsure.domain.aggregates.policy import PolicyActivated, PolicyAggregate
from openinsure.domain.aggregates.submission import (
    SubmissionAggregate,
    SubmissionBound,
    SubmissionDeclined,
)
from openinsure.domain.events import (
    ClaimClosed,
    ClaimPaid,
    ClaimReported,
    ClaimReserved,
    PolicyBound,
    PolicyCancelled,
    PolicyEndorsed,
    PolicyRenewed,
    SubmissionQuoted,
    SubmissionReceived,
    SubmissionTriaged,
)
from openinsure.domain.state_machine import InvalidTransitionError


# ---------------------------------------------------------------------------
# SubmissionAggregate
# ---------------------------------------------------------------------------


class TestSubmissionAggregate:
    """Test the Submission aggregate root."""

    def _make_submission(self, **overrides: object) -> dict:
        data = {
            "id": str(uuid4()),
            "status": "received",
            "line_of_business": "cyber",
            "quoted_premium": None,
            "triage_result": None,
        }
        data.update(overrides)
        return data

    def test_receive_emits_event(self) -> None:
        agg = SubmissionAggregate(self._make_submission())
        agg.receive()
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], SubmissionReceived)
        assert events[0].event_type == "submission.received"

    def test_triage_transitions_to_underwriting(self) -> None:
        agg = SubmissionAggregate(self._make_submission())
        agg.triage({"risk_score": 5, "recommendation": "proceed"})
        assert agg.status == "underwriting"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], SubmissionTriaged)

    def test_quote_sets_premium_and_emits(self) -> None:
        agg = SubmissionAggregate(self._make_submission(status="underwriting"))
        agg.quote(15000.0)
        assert agg.status == "quoted"
        assert agg.data["quoted_premium"] == 15000.0
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], SubmissionQuoted)

    def test_quote_rejects_zero_premium(self) -> None:
        agg = SubmissionAggregate(self._make_submission(status="underwriting"))
        with pytest.raises(ValueError, match="Premium must be positive"):
            agg.quote(0)

    def test_quote_rejects_negative_premium(self) -> None:
        agg = SubmissionAggregate(self._make_submission(status="underwriting"))
        with pytest.raises(ValueError, match="Premium must be positive"):
            agg.quote(-100)

    def test_bind_emits_submission_bound(self) -> None:
        agg = SubmissionAggregate(
            self._make_submission(status="quoted", quoted_premium=10000, triage_result={"risk_score": 5})
        )
        agg.bind(policy_id="pol-1", policy_number="POL-2025-ABC", premium=10000)
        assert agg.status == "bound"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], SubmissionBound)
        assert events[0].event_type == "submission.bound"
        assert events[0].payload["policy_id"] == "pol-1"
        assert events[0].payload["premium"] == 10000

    def test_decline_emits_event(self) -> None:
        agg = SubmissionAggregate(self._make_submission())
        agg.decline(reason="outside appetite")
        assert agg.status == "declined"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], SubmissionDeclined)
        assert events[0].payload["reason"] == "outside appetite"

    def test_invalid_transition_raises(self) -> None:
        agg = SubmissionAggregate(self._make_submission(status="bound"))
        with pytest.raises(InvalidTransitionError):
            agg.triage({})

    def test_clear_events_returns_and_clears(self) -> None:
        agg = SubmissionAggregate(self._make_submission())
        agg.receive()
        events = agg.clear_events()
        assert len(events) == 1
        assert agg.pending_events == []

    def test_full_lifecycle(self) -> None:
        """Test the complete happy path: receive → triage → quote → bind."""
        agg = SubmissionAggregate(self._make_submission())
        agg.triage({"risk_score": 3})
        agg.quote(12000.0)
        agg.bind(policy_id="p1", policy_number="POL-2025-X", premium=12000.0)
        events = agg.pending_events
        assert len(events) == 3
        assert events[0].event_type == "submission.triaged"
        assert events[1].event_type == "submission.quoted"
        assert events[2].event_type == "submission.bound"


# ---------------------------------------------------------------------------
# PolicyAggregate
# ---------------------------------------------------------------------------


class TestPolicyAggregate:
    """Test the Policy aggregate root."""

    def _make_policy(self, **overrides: object) -> dict:
        data = {
            "id": str(uuid4()),
            "policy_number": "POL-2025-TEST",
            "status": "pending",
            "effective_date": "2025-01-01",
            "expiration_date": "2026-01-01",
            "total_premium": 10000,
            "premium": 10000,
        }
        data.update(overrides)
        return data

    def test_activate_transitions_to_active(self) -> None:
        agg = PolicyAggregate(self._make_policy())
        agg.activate()
        assert agg.status == "active"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], PolicyActivated)

    def test_bind_sets_active_and_emits(self) -> None:
        agg = PolicyAggregate(self._make_policy())
        agg.bind(submission_id="sub-1", premium=15000)
        assert agg.status == "active"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], PolicyBound)
        assert events[0].payload["premium"] == 15000

    def test_endorse_on_active_policy(self) -> None:
        agg = PolicyAggregate(self._make_policy(status="active"))
        agg.endorse({"endorsement_number": "END-001", "description": "Add coverage"})
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], PolicyEndorsed)
        assert len(agg.data["endorsements"]) == 1

    def test_endorse_on_non_active_raises(self) -> None:
        agg = PolicyAggregate(self._make_policy(status="pending"))
        with pytest.raises(InvalidTransitionError):
            agg.endorse({"endorsement_number": "END-001"})

    def test_cancel_active_policy(self) -> None:
        agg = PolicyAggregate(self._make_policy(status="active"))
        agg.cancel(reason="Non-payment")
        assert agg.status == "cancelled"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], PolicyCancelled)

    def test_renew_emits_event(self) -> None:
        agg = PolicyAggregate(self._make_policy(status="active"))
        agg.renew(new_policy_id="new-pol-1")
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], PolicyRenewed)
        assert events[0].payload["new_policy_id"] == "new-pol-1"

    def test_invalid_cancel_from_pending(self) -> None:
        """Pending → cancelled is not a valid transition."""
        agg = PolicyAggregate(self._make_policy(status="pending"))
        with pytest.raises(InvalidTransitionError):
            agg.cancel(reason="test")

    def test_clear_events(self) -> None:
        agg = PolicyAggregate(self._make_policy())
        agg.activate()
        events = agg.clear_events()
        assert len(events) == 1
        assert agg.pending_events == []


# ---------------------------------------------------------------------------
# ClaimAggregate
# ---------------------------------------------------------------------------


class TestClaimAggregate:
    """Test the Claim aggregate root."""

    def _make_claim(self, **overrides: object) -> dict:
        data = {
            "id": str(uuid4()),
            "claim_number": "CLM-2025-001",
            "status": "reported",
            "policy_id": str(uuid4()),
            "reserves": [],
            "payments": [],
        }
        data.update(overrides)
        return data

    def test_report_emits_event(self) -> None:
        agg = ClaimAggregate(self._make_claim())
        agg.report()
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], ClaimReported)

    def test_investigate_transitions(self) -> None:
        agg = ClaimAggregate(self._make_claim())
        agg.investigate()
        assert agg.status == "investigating"

    def test_set_reserve(self) -> None:
        agg = ClaimAggregate(self._make_claim(status="investigating"))
        agg.set_reserve({"reserve_type": "indemnity", "amount": 50000})
        assert agg.status == "reserved"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], ClaimReserved)
        assert len(agg.data["reserves"]) == 1

    def test_negative_reserve_raises(self) -> None:
        agg = ClaimAggregate(self._make_claim(status="investigating"))
        with pytest.raises(ValueError, match="negative"):
            agg.set_reserve({"reserve_type": "indemnity", "amount": -100})

    def test_make_payment(self) -> None:
        agg = ClaimAggregate(self._make_claim(status="reserved"))
        agg.make_payment({"amount": 25000, "payee_id": str(uuid4())})
        assert agg.status == "settling"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], ClaimPaid)

    def test_deny_claim(self) -> None:
        agg = ClaimAggregate(self._make_claim(status="investigating"))
        agg.deny(reason="Coverage exclusion applies")
        assert agg.status == "denied"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], ClaimDenied)
        assert events[0].payload["reason"] == "Coverage exclusion applies"

    def test_close_claim(self) -> None:
        agg = ClaimAggregate(self._make_claim(status="settling"))
        agg.close(reason="Fully settled")
        assert agg.status == "closed"
        events = agg.pending_events
        assert len(events) == 1
        assert isinstance(events[0], ClaimClosed)

    def test_invalid_transition_raises(self) -> None:
        agg = ClaimAggregate(self._make_claim(status="closed"))
        with pytest.raises(InvalidTransitionError):
            agg.investigate()

    def test_full_lifecycle(self) -> None:
        """reported → investigating → reserved → settling → closed."""
        agg = ClaimAggregate(self._make_claim())
        agg.investigate()
        agg.set_reserve({"reserve_type": "indemnity", "amount": 50000})
        agg.make_payment({"amount": 50000})
        agg.close(reason="Paid in full")
        assert agg.status == "closed"
        events = agg.pending_events
        # investigate has no event, set_reserve (1), make_payment (1), close (1)
        assert len(events) == 3
