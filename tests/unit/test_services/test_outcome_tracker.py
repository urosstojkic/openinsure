"""Tests for Decision Outcome Tracking (#179)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from openinsure.services.outcome_tracker import (
    _in_memory_outcomes,
    get_accuracy_report,
    get_outcomes_for_decision,
    record_claim_filed_outcome,
    record_outcome,
    record_renewal_outcome,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_in_memory_outcomes():
    """Reset in-memory outcome store between tests."""
    _in_memory_outcomes.clear()
    yield
    _in_memory_outcomes.clear()


@pytest.fixture(autouse=True)
def _no_sql(monkeypatch):
    """Ensure no real SQL connections unless explicitly patched."""
    monkeypatch.setattr(
        "openinsure.services.outcome_tracker.get_database_adapter",
        lambda: None,
    )


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------


class TestRecordOutcome:
    @pytest.mark.asyncio
    async def test_records_to_sql(self) -> None:
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(return_value=1)
        decision_id = str(uuid4())

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=mock_db):
            result = await record_outcome(
                decision_id=decision_id,
                outcome_type="claim_filed",
                outcome_value=50000.0,
                accuracy_score=0.3,
                notes="Test claim filed",
            )

        assert result is not None
        assert result["decision_id"] == decision_id
        assert result["outcome_type"] == "claim_filed"
        assert result["accuracy_score"] == 0.3
        mock_db.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_records_to_in_memory_when_no_sql(self) -> None:
        decision_id = str(uuid4())

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=None):
            result = await record_outcome(
                decision_id=decision_id,
                outcome_type="renewal_retained",
                accuracy_score=0.85,
            )

        assert result is not None
        assert len(_in_memory_outcomes) == 1
        assert _in_memory_outcomes[0]["decision_id"] == decision_id

    @pytest.mark.asyncio
    async def test_sql_failure_returns_none(self) -> None:
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(side_effect=Exception("DB error"))

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=mock_db):
            result = await record_outcome(
                decision_id=str(uuid4()),
                outcome_type="claim_filed",
            )

        assert result is None


# ---------------------------------------------------------------------------
# record_claim_filed_outcome
# ---------------------------------------------------------------------------


class TestRecordClaimFiledOutcome:
    @pytest.mark.asyncio
    async def test_skips_when_no_database(self) -> None:
        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=None):
            outcomes = await record_claim_filed_outcome(
                policy_id=str(uuid4()),
                claim_id=str(uuid4()),
            )
        assert outcomes == []

    @pytest.mark.asyncio
    async def test_finds_and_records_decisions(self) -> None:
        policy_id = str(uuid4())
        claim_id = str(uuid4())
        decision_id = str(uuid4())

        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {
                    "decision_id": decision_id,
                    "decision_type": "triage",
                    "confidence": 0.9,
                }
            ]
        )
        mock_db.execute_query = AsyncMock(return_value=1)

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=mock_db):
            outcomes = await record_claim_filed_outcome(
                policy_id=policy_id,
                claim_id=claim_id,
                loss_amount=25000.0,
            )

        assert len(outcomes) == 1
        assert outcomes[0]["outcome_type"] == "claim_filed"
        # High confidence triage + claim filed = lower accuracy
        assert outcomes[0]["accuracy_score"] == pytest.approx(0.1, abs=0.01)


# ---------------------------------------------------------------------------
# record_renewal_outcome
# ---------------------------------------------------------------------------


class TestRecordRenewalOutcome:
    @pytest.mark.asyncio
    async def test_skips_when_no_database(self) -> None:
        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=None):
            outcomes = await record_renewal_outcome(policy_id=str(uuid4()))
        assert outcomes == []

    @pytest.mark.asyncio
    async def test_records_renewal_retained(self) -> None:
        policy_id = str(uuid4())
        decision_id = str(uuid4())

        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {
                    "decision_id": decision_id,
                    "decision_type": "underwriting",
                    "confidence": 0.8,
                }
            ]
        )
        mock_db.execute_query = AsyncMock(return_value=1)

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=mock_db):
            outcomes = await record_renewal_outcome(policy_id=policy_id)

        assert len(outcomes) == 1
        assert outcomes[0]["outcome_type"] == "renewal_retained"
        assert outcomes[0]["accuracy_score"] == pytest.approx(0.9, abs=0.01)


# ---------------------------------------------------------------------------
# get_outcomes_for_decision
# ---------------------------------------------------------------------------


class TestGetOutcomesForDecision:
    @pytest.mark.asyncio
    async def test_returns_sql_results(self) -> None:
        from datetime import UTC, datetime

        decision_id = str(uuid4())
        outcome_id = str(uuid4())
        now = datetime.now(UTC)

        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": outcome_id,
                    "decision_id": decision_id,
                    "outcome_type": "claim_filed",
                    "outcome_value": 50000.0,
                    "accuracy_score": 0.3,
                    "measured_at": now,
                    "notes": "test",
                }
            ]
        )

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=mock_db):
            results = await get_outcomes_for_decision(decision_id)

        assert len(results) == 1
        assert results[0]["outcome_type"] == "claim_filed"
        assert results[0]["accuracy_score"] == 0.3

    @pytest.mark.asyncio
    async def test_returns_in_memory_results(self) -> None:
        decision_id = str(uuid4())
        _in_memory_outcomes.append(
            {
                "id": str(uuid4()),
                "decision_id": decision_id,
                "outcome_type": "renewal_retained",
                "outcome_value": None,
                "accuracy_score": 0.9,
                "measured_at": "2025-01-01T00:00:00",
                "notes": None,
            }
        )

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=None):
            results = await get_outcomes_for_decision(decision_id)

        assert len(results) == 1
        assert results[0]["outcome_type"] == "renewal_retained"


# ---------------------------------------------------------------------------
# get_accuracy_report
# ---------------------------------------------------------------------------


class TestGetAccuracyReport:
    @pytest.mark.asyncio
    async def test_in_memory_report(self) -> None:
        d1 = str(uuid4())
        d2 = str(uuid4())
        _in_memory_outcomes.extend(
            [
                {
                    "id": str(uuid4()),
                    "decision_id": d1,
                    "outcome_type": "claim_filed",
                    "outcome_value": 10000.0,
                    "accuracy_score": 0.3,
                    "measured_at": "2025-01-01",
                    "notes": None,
                },
                {
                    "id": str(uuid4()),
                    "decision_id": d2,
                    "outcome_type": "renewal_retained",
                    "outcome_value": None,
                    "accuracy_score": 0.9,
                    "measured_at": "2025-02-01",
                    "notes": None,
                },
            ]
        )

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=None):
            report = await get_accuracy_report()

        assert report["overall"]["total_outcomes"] == 2
        assert report["overall"]["decisions_measured"] == 2
        assert report["overall"]["avg_accuracy"] == pytest.approx(0.6, abs=0.01)
        assert len(report["by_agent"]) == 2

    @pytest.mark.asyncio
    async def test_sql_report(self) -> None:
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {
                    "agent_id": "triage-agent",
                    "outcome_type": "claim_filed",
                    "outcome_count": 10,
                    "avg_accuracy": 0.65,
                    "min_accuracy": 0.2,
                    "max_accuracy": 0.95,
                }
            ]
        )
        mock_db.fetch_one = AsyncMock(
            return_value={
                "total_outcomes": 10,
                "avg_accuracy": 0.65,
                "decisions_measured": 8,
            }
        )

        with patch("openinsure.services.outcome_tracker.get_database_adapter", return_value=mock_db):
            report = await get_accuracy_report()

        assert report["overall"]["total_outcomes"] == 10
        assert report["overall"]["avg_accuracy"] == 0.65
        assert len(report["by_agent"]) == 1
        assert report["by_agent"][0]["agent_id"] == "triage-agent"


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


class TestComplianceOutcomeEndpoints:
    @pytest.mark.asyncio
    async def test_decision_outcomes_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from openinsure.main import create_app

        app = create_app()
        client = TestClient(app)
        decision_id = str(uuid4())

        with patch(
            "openinsure.services.outcome_tracker.get_outcomes_for_decision",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": str(uuid4()),
                    "decision_id": decision_id,
                    "outcome_type": "claim_filed",
                    "outcome_value": 50000.0,
                    "accuracy_score": 0.3,
                    "measured_at": "2025-01-01T00:00:00",
                    "notes": None,
                }
            ],
        ):
            resp = client.get(
                f"/api/v1/compliance/decision-outcomes?decision_id={decision_id}",
                headers={"X-User-Role": "admin"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision_id"] == decision_id
        assert body["count"] == 1
        assert body["items"][0]["outcome_type"] == "claim_filed"

    @pytest.mark.asyncio
    async def test_accuracy_report_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from openinsure.main import create_app

        app = create_app()
        client = TestClient(app)

        with patch(
            "openinsure.services.outcome_tracker.get_accuracy_report",
            new_callable=AsyncMock,
            return_value={
                "generated_at": "2025-01-01T00:00:00",
                "overall": {
                    "total_outcomes": 5,
                    "avg_accuracy": 0.72,
                    "decisions_measured": 4,
                },
                "by_agent": [
                    {
                        "agent_id": "triage-agent",
                        "outcome_type": "claim_filed",
                        "outcome_count": 3,
                        "avg_accuracy": 0.65,
                        "min_accuracy": 0.3,
                        "max_accuracy": 0.9,
                    }
                ],
            },
        ):
            resp = client.get(
                "/api/v1/compliance/accuracy-report",
                headers={"X-User-Role": "admin"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["overall"]["total_outcomes"] == 5
        assert body["overall"]["avg_accuracy"] == 0.72
        assert len(body["by_agent"]) == 1
