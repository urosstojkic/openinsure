"""Tests for bind event handlers (DDD cross-aggregate side-effects).

Covers:
- PolicyCreationHandler
- BillingHandler
- ReinsuranceHandler
- dispatch_bind_events orchestration
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from openinsure.domain.aggregates.submission import SubmissionBound
from openinsure.services.bind_handlers import (
    BillingHandler,
    PolicyCreationHandler,
    ReinsuranceHandler,
    dispatch_bind_events,
)


def _make_submission_bound_event(**payload_overrides: object) -> SubmissionBound:
    """Create a SubmissionBound event for testing."""
    payload = {
        "submission_id": str(uuid4()),
        "policy_id": str(uuid4()),
        "policy_number": "POL-2025-TEST",
        "premium": 10000,
    }
    payload.update(payload_overrides)
    return SubmissionBound.create(
        submission_id=uuid4(),
        payload=payload,
    )


class TestPolicyCreationHandler:
    """Test PolicyCreationHandler."""

    @pytest.mark.asyncio
    async def test_creates_policy(self) -> None:
        handler = PolicyCreationHandler()
        event = _make_submission_bound_event()
        mock_repo = AsyncMock()
        policy_data = {"id": str(uuid4()), "status": "active"}
        ctx = {"policy_repo": mock_repo, "policy_data": policy_data}

        result = await handler.handle(event, ctx)

        mock_repo.create.assert_awaited_once_with(policy_data)
        assert result == policy_data

    @pytest.mark.asyncio
    async def test_creates_policy_with_txn(self) -> None:
        handler = PolicyCreationHandler()
        event = _make_submission_bound_event()
        mock_repo = AsyncMock()
        mock_txn = object()
        policy_data = {"id": str(uuid4()), "status": "active"}
        ctx = {"policy_repo": mock_repo, "policy_data": policy_data, "txn": mock_txn}

        await handler.handle(event, ctx)

        mock_repo.create.assert_awaited_once_with(policy_data, txn=mock_txn)

    @pytest.mark.asyncio
    async def test_ignores_non_bound_events(self) -> None:
        from openinsure.domain.events import SubmissionTriaged

        handler = PolicyCreationHandler()
        event = SubmissionTriaged.create(uuid4())
        result = await handler.handle(event, {})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_context_returns_none(self) -> None:
        handler = PolicyCreationHandler()
        event = _make_submission_bound_event()
        result = await handler.handle(event, {})
        assert result is None


class TestBillingHandler:
    """Test BillingHandler."""

    @pytest.mark.asyncio
    async def test_creates_billing(self) -> None:
        handler = BillingHandler()
        event = _make_submission_bound_event()
        mock_fn = AsyncMock()
        ctx = {
            "billing_create_fn": mock_fn,
            "policy_id": "pol-1",
            "policyholder_name": "Acme Corp",
            "total_premium": 10000,
            "installments": 4,
            "effective_date": "2025-01-01",
        }

        result = await handler.handle(event, ctx)

        mock_fn.assert_awaited_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["policy_id"] == "pol-1"
        assert call_kwargs["total_premium"] == 10000
        assert call_kwargs["installments"] == 4
        assert result is not None
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_no_billing_fn_returns_none(self) -> None:
        handler = BillingHandler()
        event = _make_submission_bound_event()
        result = await handler.handle(event, {})
        assert result is None


class TestReinsuranceHandler:
    """Test ReinsuranceHandler."""

    @pytest.mark.asyncio
    async def test_creates_cessions(self) -> None:
        handler = ReinsuranceHandler()
        event = _make_submission_bound_event()
        mock_fn = AsyncMock()
        ctx = {
            "cession_fn": mock_fn,
            "policy_id": "pol-1",
            "policy_number": "POL-2025-X",
            "policy_data": {"id": "pol-1", "premium": 10000},
        }

        result = await handler.handle(event, ctx)

        mock_fn.assert_awaited_once_with("pol-1", "POL-2025-X", {"id": "pol-1", "premium": 10000})
        assert result is not None

    @pytest.mark.asyncio
    async def test_failure_returns_none(self) -> None:
        handler = ReinsuranceHandler()
        event = _make_submission_bound_event()
        mock_fn = AsyncMock(side_effect=Exception("Treaty lookup failed"))
        ctx = {
            "cession_fn": mock_fn,
            "policy_id": "pol-1",
            "policy_number": "POL-2025-X",
            "policy_data": {},
        }

        # Should not raise — reinsurance is best-effort
        result = await handler.handle(event, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_cession_fn_returns_none(self) -> None:
        handler = ReinsuranceHandler()
        event = _make_submission_bound_event()
        result = await handler.handle(event, {})
        assert result is None


class TestDispatchBindEvents:
    """Test dispatch_bind_events orchestration."""

    @pytest.mark.asyncio
    async def test_dispatches_all_handlers(self) -> None:
        event = _make_submission_bound_event()
        mock_policy_repo = AsyncMock()
        mock_billing_fn = AsyncMock()
        policy_data = {"id": "pol-1", "policy_number": "POL-2025-X", "status": "active"}

        ctx = {
            "policy_repo": mock_policy_repo,
            "policy_data": policy_data,
            "billing_create_fn": mock_billing_fn,
            "policy_id": "pol-1",
            "policyholder_name": "Test Corp",
            "total_premium": 10000,
            "installments": 1,
            "effective_date": "2025-01-01",
        }

        results = await dispatch_bind_events([event], ctx)

        assert results["policy"] is not None
        assert results["billing"] is not None
        mock_policy_repo.create.assert_awaited_once()
        mock_billing_fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_non_bound_events(self) -> None:
        from openinsure.domain.events import SubmissionTriaged

        event = SubmissionTriaged.create(uuid4())
        results = await dispatch_bind_events([event], {})
        assert results == {}
