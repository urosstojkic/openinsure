"""Tests for the Event Store — persistence and replay of domain events (#171)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from openinsure.services.event_publisher import (
    _parse_aggregate,
    _recent_events,
    get_events_for_aggregate,
    get_recent_events,
    publish_domain_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_ring_buffer():
    """Reset in-memory ring buffer between tests."""
    _recent_events.clear()
    yield
    _recent_events.clear()


@pytest.fixture(autouse=True)
def _no_sql(monkeypatch):
    """Ensure no SQL persistence in basic tests (patched explicitly when needed)."""
    monkeypatch.setattr(
        "openinsure.services.event_publisher.get_database_adapter",
        lambda: None,
    )
    monkeypatch.setattr(
        "openinsure.services.event_publisher.get_event_bus",
        lambda: None,
    )


# ---------------------------------------------------------------------------
# _parse_aggregate
# ---------------------------------------------------------------------------


class TestParseAggregate:
    def test_subject_with_uuid(self) -> None:
        uid = str(uuid4())
        agg_type, agg_id = _parse_aggregate(f"/submissions/{uid}", {})
        assert agg_type == "submissions"
        assert agg_id == uid

    def test_subject_with_nested_path(self) -> None:
        uid = str(uuid4())
        agg_type, agg_id = _parse_aggregate(f"/policies/{uid}/endorsements", {})
        assert agg_type == "policies"
        assert agg_id == uid

    def test_falls_back_to_data_id(self) -> None:
        uid = str(uuid4())
        agg_type, agg_id = _parse_aggregate("/compliance/bias-report", {"id": uid})
        assert agg_type == "compliance"
        assert agg_id == uid

    def test_falls_back_to_data_submission_id(self) -> None:
        uid = str(uuid4())
        agg_type, agg_id = _parse_aggregate("/workflow", {"submission_id": uid})
        assert agg_type == "workflow"
        assert agg_id == uid

    def test_no_aggregate_id_returns_none(self) -> None:
        agg_type, agg_id = _parse_aggregate("/unknown", {"foo": "bar"})
        assert agg_type == "unknown"
        assert agg_id is None


# ---------------------------------------------------------------------------
# publish_domain_event
# ---------------------------------------------------------------------------


class TestPublishDomainEvent:
    @pytest.mark.asyncio
    async def test_stores_in_ring_buffer(self) -> None:
        await publish_domain_event("test.event", "/tests/123", {"key": "value"})
        events = get_recent_events(10)
        assert len(events) == 1
        assert events[0]["event_type"] == "test.event"
        assert events[0]["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_ring_buffer_limit(self) -> None:
        for i in range(150):
            await publish_domain_event(f"test.event.{i}", f"/tests/{i}", {"i": i})
        events = get_recent_events(200)
        # Ring buffer caps at _MAX_EVENTS = 100
        assert len(events) == 100
        # Most recent event should be first (reversed)
        assert events[0]["event_type"] == "test.event.149"

    @pytest.mark.asyncio
    async def test_persists_to_sql_when_available(self) -> None:
        uid = str(uuid4())
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(return_value=1)

        with (
            patch("openinsure.services.event_publisher.get_database_adapter", return_value=mock_db),
            patch("openinsure.services.event_publisher.get_event_bus", return_value=None),
        ):
            await publish_domain_event(
                "submission.created",
                f"/submissions/{uid}",
                {"submission_id": uid},
            )

        mock_db.execute_query.assert_called_once()
        call_args = mock_db.execute_query.call_args
        assert "INSERT INTO domain_events" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_skips_persistence_without_aggregate_id(self) -> None:
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(return_value=1)

        with (
            patch("openinsure.services.event_publisher.get_database_adapter", return_value=mock_db),
            patch("openinsure.services.event_publisher.get_event_bus", return_value=None),
        ):
            await publish_domain_event(
                "system.heartbeat",
                "/system",
                {"status": "ok"},
            )

        # No aggregate ID derivable → no SQL insert
        mock_db.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_failure_non_critical(self) -> None:
        uid = str(uuid4())
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(side_effect=Exception("DB down"))

        with (
            patch("openinsure.services.event_publisher.get_database_adapter", return_value=mock_db),
            patch("openinsure.services.event_publisher.get_event_bus", return_value=None),
        ):
            # Should not raise
            await publish_domain_event(
                "test.event",
                f"/tests/{uid}",
                {"id": uid},
            )

        # Event is still in ring buffer even though SQL failed
        assert len(get_recent_events(10)) == 1


# ---------------------------------------------------------------------------
# get_events_for_aggregate
# ---------------------------------------------------------------------------


class TestGetEventsForAggregate:
    @pytest.mark.asyncio
    async def test_queries_sql_when_available(self) -> None:
        uid = str(uuid4())
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "event_id": uuid4(),
                    "event_type": "submission.created",
                    "aggregate_type": "submissions",
                    "aggregate_id": uid,
                    "version": 1,
                    "payload": json.dumps({"id": uid}),
                    "metadata": json.dumps({"subject": f"/submissions/{uid}"}),
                    "actor": None,
                    "occurred_at": "2025-01-01T00:00:00",
                },
            ]
        )

        with patch("openinsure.services.event_publisher.get_database_adapter", return_value=mock_db):
            events = await get_events_for_aggregate(uid, "submissions")

        assert len(events) == 1
        assert events[0]["event_type"] == "submission.created"
        assert events[0]["aggregate_id"] == uid
        mock_db.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_ring_buffer(self) -> None:
        uid = str(uuid4())
        _recent_events.append(
            {
                "event_type": "test.event",
                "subject": f"/tests/{uid}",
                "data": {"id": uid},
                "timestamp": "2025-01-01T00:00:00",
            }
        )

        with patch("openinsure.services.event_publisher.get_database_adapter", return_value=None):
            events = await get_events_for_aggregate(uid)

        assert len(events) == 1
        assert events[0]["data"]["id"] == uid


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------


class TestEventsAPI:
    @pytest.mark.asyncio
    async def test_replay_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from openinsure.main import create_app

        app = create_app()
        client = TestClient(app)
        uid = str(uuid4())

        with patch(
            "openinsure.services.event_publisher.get_events_for_aggregate",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": 1,
                    "event_id": str(uuid4()),
                    "event_type": "test.created",
                    "aggregate_type": "tests",
                    "aggregate_id": uid,
                    "version": 1,
                    "payload": {"test": True},
                    "metadata": None,
                    "actor": None,
                    "occurred_at": "2025-01-01T00:00:00",
                }
            ],
        ):
            resp = client.get(
                f"/api/v1/events?aggregate_id={uid}",
                headers={"X-User-Role": "admin"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["aggregate_id"] == uid
        assert body["count"] == 1
        assert body["events"][0]["event_type"] == "test.created"
