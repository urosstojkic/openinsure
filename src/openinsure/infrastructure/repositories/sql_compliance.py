"""SQL-backed compliance repository using Azure SQL Database."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openinsure.infrastructure.repository import safe_pagination_clause

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter


class SqlComplianceRepository:
    """Azure SQL implementation of the compliance (decisions + audit) repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    # -- decisions -----------------------------------------------------------

    async def add_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        await self.db.execute_query(
            """INSERT INTO decision_records (id, decision_type, entity_id, entity_type,
               model_id, model_version, input_summary, output_summary, confidence,
               explanation, human_override, override_reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                decision["id"],
                decision.get("decision_type"),
                decision.get("entity_id"),
                decision.get("entity_type"),
                decision.get("model_id"),
                decision.get("model_version"),
                json.dumps(decision.get("input_summary", {})),
                json.dumps(decision.get("output_summary", {})),
                decision.get("confidence"),
                decision.get("explanation"),
                decision.get("human_override", False),
                decision.get("override_reason"),
                decision.get("created_at"),
            ],
        )
        return decision

    async def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM decision_records WHERE id = ?", [decision_id])
        if row:
            row = _deserialize_decision(row)
        return row

    async def list_decisions(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        count_query = "SELECT COUNT(*) as cnt FROM decision_records"
        query = "SELECT * FROM decision_records"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "decision_type" in filters:
                where_clauses.append("decision_type = ?")
                params.append(filters["decision_type"])
            if "entity_type" in filters:
                where_clauses.append("entity_type = ?")
                params.append(filters["entity_type"])
            if "entity_id" in filters:
                where_clauses.append("entity_id = ?")
                params.append(filters["entity_id"])
        if where_clauses:
            clause = " WHERE " + " AND ".join(where_clauses)
            query += clause
            count_query += clause

        count_result = await self.db.fetch_one(count_query, params)
        total = count_result.get("cnt", 0) if count_result else 0

        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_deserialize_decision(r) for r in rows], total

    async def count_decisions(self, filters: dict[str, Any] | None = None) -> int:
        _, total = await self.list_decisions(filters=filters, skip=0, limit=1)
        return total

    # -- audit events --------------------------------------------------------

    async def add_audit_event(self, event: dict[str, Any]) -> dict[str, Any]:
        await self.db.execute_query(
            """INSERT INTO audit_events (id, timestamp, actor, action,
               entity_type, entity_id, details)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                event["id"],
                event.get("timestamp"),
                event.get("actor"),
                event.get("action"),
                event.get("entity_type"),
                event.get("entity_id"),
                json.dumps(event.get("details", {})),
            ],
        )
        return event

    async def list_audit_events(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        count_query = "SELECT COUNT(*) as cnt FROM audit_events"
        query = "SELECT * FROM audit_events"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "entity_type" in filters:
                where_clauses.append("entity_type = ?")
                params.append(filters["entity_type"])
            if "entity_id" in filters:
                where_clauses.append("entity_id = ?")
                params.append(filters["entity_id"])
            if "actor" in filters:
                where_clauses.append("actor = ?")
                params.append(filters["actor"])
            if "action" in filters:
                where_clauses.append("action = ?")
                params.append(filters["action"])
        if where_clauses:
            clause = " WHERE " + " AND ".join(where_clauses)
            query += clause
            count_query += clause

        count_result = await self.db.fetch_one(count_query, params)
        total = count_result.get("cnt", 0) if count_result else 0

        pag_clause, pag_params = safe_pagination_clause("timestamp DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_deserialize_audit_event(r) for r in rows], total

    async def clear_audit_events(self) -> None:
        await self.db.execute_query("DELETE FROM audit_events")

    # -- agent-level persistence (wired from agents.base → Foundry flow) ------

    async def store_decision(self, record: dict[str, Any]) -> str:
        """Persist an agent DecisionRecord to the decision_records table."""
        record_id = str(record.get("decision_id", record.get("id", "")))
        await self.db.execute_query(
            """INSERT INTO decision_records (id, decision_type, entity_id, entity_type,
               model_id, model_version, input_summary, output_summary, confidence,
               explanation, human_override, override_reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                record_id,
                record.get("decision_type"),
                record.get("entity_id", record.get("agent_id", "")),
                record.get("entity_type", "agent"),
                record.get("model_used", record.get("model_id", "")),
                record.get("model_version"),
                json.dumps(record.get("input_summary", {})),
                json.dumps(record.get("output", record.get("output_summary", {}))),
                record.get("confidence", 0),
                json.dumps(record.get("reasoning", {})),
                bool(record.get("human_override", False)),
                record.get("override_reason"),
                record.get("created_at", record.get("timestamp", "")),
            ],
        )
        return record_id

    async def store_audit_event(self, event: dict[str, Any]) -> str:
        """Persist an audit event from the agent workflow."""
        from uuid import uuid4

        event_id = str(event.get("id", uuid4()))
        await self.db.execute_query(
            """INSERT INTO audit_events (id, timestamp, actor, action,
               entity_type, entity_id, details)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                event_id,
                event.get("timestamp", event.get("created_at", "")),
                event.get("actor", event.get("actor_id", "agent")),
                event.get("action", ""),
                event.get("entity_type", event.get("resource_type", "")),
                event.get("entity_id", event.get("resource_id", "")),
                json.dumps(event.get("details", {})),
            ],
        )
        return event_id


def _deserialize_decision(row: dict[str, Any]) -> dict[str, Any]:
    for col in ("input_summary", "output_summary"):
        if col in row and isinstance(row[col], str):
            row[col] = json.loads(row[col])
    return row


def _deserialize_audit_event(row: dict[str, Any]) -> dict[str, Any]:
    if "details" in row and isinstance(row["details"], str):
        row["details"] = json.loads(row["details"])
    return row
