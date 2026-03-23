"""Tests for the automated renewal scheduler."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openinsure.services.renewal_scheduler import (
    _renewal_queue,
    get_renewal_queue,
    identify_and_queue_renewals,
)


def _make_policy(policy_id: str, days_to_expiry: int) -> dict[str, Any]:
    exp_date = date.today() + timedelta(days=days_to_expiry)
    return {
        "id": policy_id,
        "policy_number": f"POL-{policy_id}",
        "policyholder_name": f"Company {policy_id}",
        "status": "active",
        "effective_date": str(exp_date - timedelta(days=365)),
        "expiration_date": str(exp_date),
        "premium": 10000,
        "total_premium": 10000,
    }


@pytest.mark.asyncio
class TestIdentifyAndQueueRenewals:
    def setup_method(self, method: Any) -> None:
        _renewal_queue.clear()

    @patch("openinsure.services.renewal_scheduler.get_renewal_repository")
    @patch("openinsure.services.renewal_scheduler.get_policy_repository")
    async def test_identifies_expiring_policies(
        self, mock_policy_repo: MagicMock, mock_renewal_repo: MagicMock
    ) -> None:
        policies = [
            _make_policy("pol-1", 25),  # urgent (<=30)
            _make_policy("pol-2", 55),  # terms_due (<=60)
            _make_policy("pol-3", 85),  # pending (<=90)
            _make_policy("pol-4", 120),  # outside window
        ]
        repo = AsyncMock()
        repo.list_all = AsyncMock(return_value=policies)
        mock_policy_repo.return_value = repo

        renewal_repo = AsyncMock()
        renewal_repo.list_all = AsyncMock(return_value=[])
        renewal_repo.create = AsyncMock()
        mock_renewal_repo.return_value = renewal_repo

        stats = await identify_and_queue_renewals()

        assert stats["urgent"] == 1
        assert stats["terms_due"] == 1
        assert stats["new_records"] == 1
        # pol-4 outside window should not be queued
        assert renewal_repo.create.call_count == 3

    @patch("openinsure.services.renewal_scheduler.get_renewal_repository")
    @patch("openinsure.services.renewal_scheduler.get_policy_repository")
    async def test_skips_cancelled_policies(self, mock_policy_repo: MagicMock, mock_renewal_repo: MagicMock) -> None:
        policy = _make_policy("pol-cancelled", 45)
        policy["status"] = "cancelled"

        repo = AsyncMock()
        repo.list_all = AsyncMock(return_value=[policy])
        mock_policy_repo.return_value = repo

        renewal_repo = AsyncMock()
        renewal_repo.list_all = AsyncMock(return_value=[])
        renewal_repo.create = AsyncMock()
        mock_renewal_repo.return_value = renewal_repo

        await identify_and_queue_renewals()

        assert renewal_repo.create.call_count == 0


@pytest.mark.asyncio
class TestGetRenewalQueue:
    async def test_filters_by_status(self) -> None:
        _renewal_queue.clear()
        _renewal_queue.extend(
            [
                {"id": "1", "status": "urgent", "days_to_expiry": 10, "policy_id": "a"},
                {"id": "2", "status": "pending", "days_to_expiry": 80, "policy_id": "b"},
            ]
        )
        result = await get_renewal_queue(status="urgent")
        assert len(result) == 1
        assert result[0]["id"] == "1"
        _renewal_queue.clear()

    async def test_sorts_by_days_to_expiry(self) -> None:
        _renewal_queue.clear()
        _renewal_queue.extend(
            [
                {"id": "1", "status": "pending", "days_to_expiry": 80, "policy_id": "a"},
                {"id": "2", "status": "urgent", "days_to_expiry": 10, "policy_id": "b"},
            ]
        )
        result = await get_renewal_queue(sort_by="days_to_expiry")
        assert result[0]["id"] == "2"
        _renewal_queue.clear()
