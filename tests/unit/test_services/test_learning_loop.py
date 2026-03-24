"""Tests for the Decision Learning Loop service."""

from __future__ import annotations

from typing import Any

import pytest

from openinsure.services.learning_loop import (
    DecisionOutcomeTracker,
    _reset_store,
    get_decision_tracker,
)


@pytest.fixture(autouse=True)
def _clean_store():
    """Reset the in-memory store before each test."""
    _reset_store()
    yield
    _reset_store()


def _make_decision(
    decision_id: str = "dec-001",
    agent_name: str = "triage",
    **overrides: Any,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "decision_id": decision_id,
        "agent_name": agent_name,
        "decision_type": "triage",
        "predicted": {"risk_score": 5, "premium": 10000},
        "submission_id": "sub-001",
    }
    defaults.update(overrides)
    return defaults


class TestDecisionOutcomeTracker:
    """Core tracker behaviour."""

    @pytest.fixture
    def tracker(self) -> DecisionOutcomeTracker:
        return DecisionOutcomeTracker()

    async def test_record_decision(self, tracker: DecisionOutcomeTracker) -> None:
        result = await tracker.record_decision(_make_decision())
        assert result == "dec-001"

    async def test_record_decision_requires_id(self, tracker: DecisionOutcomeTracker) -> None:
        with pytest.raises(ValueError, match="decision_id"):
            await tracker.record_decision({"agent_name": "triage"})

    async def test_record_outcome(self, tracker: DecisionOutcomeTracker) -> None:
        await tracker.record_decision(_make_decision())
        outcome = await tracker.record_outcome("dec-001", {"claim_filed": True, "actual_loss": 12000})
        assert outcome["decision_id"] == "dec-001"
        assert outcome["agent_name"] == "triage"
        assert "deviation" in outcome

    async def test_record_outcome_without_decision(self, tracker: DecisionOutcomeTracker) -> None:
        # Should still work — outcome can be recorded even without a prior decision
        outcome = await tracker.record_outcome("unknown-dec", {"claim_filed": False})
        assert outcome["decision_id"] == "unknown-dec"
        assert outcome["agent_name"] == "unknown"


class TestAccuracyMetrics:
    """Accuracy computation tests."""

    @pytest.fixture
    def tracker(self) -> DecisionOutcomeTracker:
        return DecisionOutcomeTracker()

    async def test_empty_metrics(self, tracker: DecisionOutcomeTracker) -> None:
        metrics = await tracker.get_accuracy_metrics("triage")
        assert metrics["total_decisions"] == 0
        assert metrics["accuracy_rate"] == 0.0

    async def test_metrics_after_outcomes(self, tracker: DecisionOutcomeTracker) -> None:
        # Record decisions and outcomes with small deviations
        for i in range(5):
            await tracker.record_decision(
                _make_decision(
                    decision_id=f"dec-{i}",
                    predicted={"risk_score": 5, "premium": 10000},
                )
            )
            # Small deviation: premium_pct=0.02 (2%), risk=0.2, overall=0.11 (<20% = correct)
            await tracker.record_outcome(
                f"dec-{i}",
                {"actual_risk_score": 5.2, "actual_loss": 10200},
            )

        metrics = await tracker.get_accuracy_metrics("triage")
        assert metrics["total_decisions"] == 5
        assert metrics["accuracy_rate"] > 0

    async def test_metrics_filter_by_agent(self, tracker: DecisionOutcomeTracker) -> None:
        await tracker.record_decision(_make_decision(decision_id="d1", agent_name="triage"))
        await tracker.record_outcome("d1", {"actual_risk_score": 6})
        await tracker.record_decision(_make_decision(decision_id="d2", agent_name="underwriting"))
        await tracker.record_outcome("d2", {"actual_risk_score": 7})

        triage = await tracker.get_accuracy_metrics("triage")
        uw = await tracker.get_accuracy_metrics("underwriting")
        assert triage["total_decisions"] == 1
        assert uw["total_decisions"] == 1


class TestImprovementSignals:
    """Tests for improvement signal detection."""

    @pytest.fixture
    def tracker(self) -> DecisionOutcomeTracker:
        return DecisionOutcomeTracker()

    async def test_no_signals_when_empty(self, tracker: DecisionOutcomeTracker) -> None:
        signals = await tracker.get_improvement_signals("triage")
        assert signals == []

    async def test_detects_pricing_bias(self, tracker: DecisionOutcomeTracker) -> None:
        # Record underpriced healthcare decisions
        for i in range(3):
            await tracker.record_decision(
                _make_decision(
                    decision_id=f"hp-{i}",
                    agent_name="underwriting",
                    predicted={"premium": 10000, "industry": "healthcare"},
                )
            )
            # Actual losses significantly higher
            await tracker.record_outcome(
                f"hp-{i}",
                {"actual_loss": 15000, "industry": "healthcare"},
            )

        signals = await tracker.get_improvement_signals("underwriting")
        # Should detect healthcare underpricing
        healthcare_signals = [s for s in signals if s.get("industry") == "healthcare"]
        assert len(healthcare_signals) >= 1
        assert healthcare_signals[0]["direction"] == "underpriced"


class TestPromptContext:
    """Tests for prompt context generation."""

    @pytest.fixture
    def tracker(self) -> DecisionOutcomeTracker:
        return DecisionOutcomeTracker()

    async def test_empty_context(self, tracker: DecisionOutcomeTracker) -> None:
        ctx = await tracker.get_prompt_context("triage")
        assert ctx == ""

    async def test_context_with_data(self, tracker: DecisionOutcomeTracker) -> None:
        for i in range(3):
            await tracker.record_decision(
                _make_decision(decision_id=f"ctx-{i}", predicted={"risk_score": 5, "premium": 10000})
            )
            await tracker.record_outcome(
                f"ctx-{i}",
                {"actual_risk_score": 6, "actual_loss": 11000},
            )

        ctx = await tracker.get_prompt_context("triage")
        assert "HISTORICAL ACCURACY" in ctx
        assert "decisions tracked" in ctx


class TestGetAllMetrics:
    """Test the aggregated metrics endpoint."""

    @pytest.fixture
    def tracker(self) -> DecisionOutcomeTracker:
        return DecisionOutcomeTracker()

    async def test_all_metrics(self, tracker: DecisionOutcomeTracker) -> None:
        await tracker.record_decision(_make_decision(decision_id="a1", agent_name="triage"))
        await tracker.record_outcome("a1", {"claim_filed": True})
        await tracker.record_decision(_make_decision(decision_id="a2", agent_name="underwriting"))
        await tracker.record_outcome("a2", {"actual_loss": 5000})

        all_m = await tracker.get_all_metrics()
        assert "agents" in all_m
        assert "triage" in all_m["agents"]
        assert "underwriting" in all_m["agents"]
        assert all_m["total_outcomes_tracked"] == 2


class TestSingleton:
    """Test the singleton factory."""

    def test_get_decision_tracker_returns_same_instance(self) -> None:
        t1 = get_decision_tracker()
        t2 = get_decision_tracker()
        assert t1 is t2
