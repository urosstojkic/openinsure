"""Tests for openinsure.services.escalation module."""

from unittest.mock import AsyncMock, patch

import pytest

from openinsure.services import escalation


@pytest.fixture(autouse=True)
def clear_queue():
    escalation._escalation_queue.clear()
    yield
    escalation._escalation_queue.clear()


async def _create_escalation(**overrides):
    defaults = dict(
        action="set_reserve",
        entity_type="claim",
        entity_id="claim-001",
        requested_by="user-1",
        requested_role="claims_adjuster",
        amount=100000.0,
        authority_result={
            "required_role": "claims_manager",
            "escalation_chain": ["claims_manager", "cuo"],
            "reason": "Amount exceeds adjuster authority",
        },
    )
    defaults.update(overrides)
    with patch("openinsure.services.work_item_service.create_work_item", new_callable=AsyncMock):
        return await escalation.escalate(**defaults)


class TestEscalation:
    async def test_escalate_creates_item(self):
        item = await _create_escalation()

        assert item["id"] is not None
        assert item["action"] == "set_reserve"
        assert item["entity_id"] == "claim-001"
        assert item["status"] == "pending"
        assert item["required_role"] == "claims_manager"
        assert len(escalation._escalation_queue) == 1

    async def test_get_queue_all(self):
        await _create_escalation(entity_id="c1")
        await _create_escalation(entity_id="c2")

        items = await escalation.get_queue()

        assert len(items) == 2

    async def test_get_queue_filtered_by_status(self):
        item = await _create_escalation()
        await escalation.resolve(item["id"], "approved", "manager-1", "Looks good")

        pending = await escalation.get_queue(status="pending")
        approved = await escalation.get_queue(status="approved")

        assert len(pending) == 0
        assert len(approved) == 1

    async def test_get_queue_filtered_by_role(self):
        await _create_escalation(
            authority_result={
                "required_role": "claims_manager",
                "escalation_chain": ["claims_manager"],
                "reason": "test",
            }
        )
        await _create_escalation(
            authority_result={
                "required_role": "cuo",
                "escalation_chain": ["cuo"],
                "reason": "test",
            }
        )

        manager_items = await escalation.get_queue(role="claims_manager")
        cuo_items = await escalation.get_queue(role="cuo")

        assert len(manager_items) == 1
        assert len(cuo_items) == 1

    async def test_get_by_id_found(self):
        item = await _create_escalation()

        found = await escalation.get_by_id(item["id"])

        assert found is not None
        assert found["id"] == item["id"]

    async def test_get_by_id_not_found(self):
        result = await escalation.get_by_id("nonexistent-id")

        assert result is None

    async def test_resolve_approve(self):
        item = await _create_escalation()

        resolved = await escalation.resolve(item["id"], "approved", "manager-1", "Approved after review")

        assert resolved is not None
        assert resolved["status"] == "approved"
        assert resolved["resolved_by"] == "manager-1"
        assert resolved["resolution_reason"] == "Approved after review"
        assert resolved["resolved_at"] is not None

    async def test_resolve_not_found(self):
        result = await escalation.resolve("nonexistent", "approved", "manager-1", "reason")

        assert result is None

    async def test_count_pending(self):
        await _create_escalation(entity_id="c1")
        await _create_escalation(entity_id="c2")
        item3 = await _create_escalation(entity_id="c3")
        await escalation.resolve(item3["id"], "approved", "mgr", "ok")

        count = await escalation.count_pending()

        assert count == 2
