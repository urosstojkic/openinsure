"""Tests for openinsure.services.audit_service.AuditService."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from openinsure.services.audit_service import AuditService, _row_to_dict


# ---------- No-DB mode ----------


class TestAuditServiceNoDb:
    async def test_log_change_no_db_noop(self):
        svc = AuditService(db=None)
        # Should not raise
        await svc.log_change(
            entity_type="claim",
            entity_id="c-001",
            action="create",
            changed_by="system",
        )

    async def test_get_history_no_db_empty(self):
        svc = AuditService(db=None)
        result = await svc.get_history("claim", "c-001")
        assert result == []

    async def test_get_recent_no_db_empty(self):
        svc = AuditService(db=None)
        result = await svc.get_recent(hours=48)
        assert result == []


# ---------- With-DB mode ----------


class TestAuditServiceWithDb:
    async def test_log_change_executes_query(self):
        db = MagicMock()
        db.execute_query = AsyncMock()
        svc = AuditService(db=db)

        await svc.log_change(
            entity_type="policy",
            entity_id="p-001",
            action="update",
            changed_by="admin",
            changes={"status": "active"},
            reason="Approved",
            ip_address="10.0.0.1",
        )

        db.execute_query.assert_awaited_once()
        call_args = db.execute_query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "INSERT INTO change_log" in sql
        assert params[1] == "policy"
        assert params[2] == "p-001"
        assert params[3] == "update"
        assert params[4] == "admin"
        assert json.loads(params[6]) == {"status": "active"}

    async def test_log_change_handles_exception(self):
        db = MagicMock()
        db.execute_query = AsyncMock(side_effect=RuntimeError("DB down"))
        svc = AuditService(db=db)

        # Should not raise — swallows exceptions
        await svc.log_change(
            entity_type="claim",
            entity_id="c-001",
            action="delete",
            changed_by="admin",
        )

    async def test_get_history_returns_results(self):
        db = MagicMock()
        db.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": "log-1",
                    "entity_type": "claim",
                    "entity_id": "c-001",
                    "action": "create",
                    "changed_by": "system",
                    "changed_at": "2025-06-01T00:00:00",
                    "changes": None,
                    "reason": None,
                    "ip_address": None,
                }
            ]
        )
        svc = AuditService(db=db)

        result = await svc.get_history("claim", "c-001")

        assert len(result) == 1
        assert result[0]["entity_type"] == "claim"
        assert result[0]["action"] == "create"


# ---------- _row_to_dict helper ----------


class TestRowToDict:
    def test_row_to_dict_basic(self):
        row = {
            "id": "abc",
            "entity_type": "policy",
            "entity_id": "p-1",
            "action": "update",
            "changed_by": "admin",
            "changed_at": "2025-06-01T12:00:00",
            "changes": None,
            "reason": "test",
            "ip_address": "10.0.0.1",
        }
        result = _row_to_dict(row)

        assert result["id"] == "abc"
        assert result["entity_type"] == "policy"
        assert result["action"] == "update"
        assert result["reason"] == "test"
        assert result["ip_address"] == "10.0.0.1"

    def test_row_to_dict_json_changes(self):
        row = {
            "id": "abc",
            "entity_type": "claim",
            "entity_id": "c-1",
            "action": "update",
            "changed_by": "system",
            "changed_at": "2025-06-01",
            "changes": json.dumps({"status": "closed", "reason": "settled"}),
            "reason": None,
            "ip_address": None,
        }
        result = _row_to_dict(row)

        assert isinstance(result["changes"], dict)
        assert result["changes"]["status"] == "closed"

    def test_row_to_dict_none_values(self):
        row = {
            "id": None,
            "entity_type": None,
            "entity_id": None,
            "action": None,
            "changed_by": None,
            "changed_at": None,
            "changes": None,
            "reason": None,
            "ip_address": None,
        }
        result = _row_to_dict(row)

        assert result["id"] == ""
        assert result["reason"] is None
        assert result["ip_address"] is None
        assert result["changes"] is None
