"""SQL-backed compliance repository using Azure SQL Database.

Maps the API-level decision fields (entity_id, model_id, output_summary,
explanation, human_override) to the actual ``decision_records`` SQL table
columns (agent_id, model_used, output_data, reasoning, human_oversight).
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID  # noqa: TC003

from openinsure.infrastructure.repository import BaseRepository, safe_pagination_clause

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter


class SqlComplianceRepository(BaseRepository):
    """Azure SQL implementation of the compliance (decisions + audit) repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    # -- BaseRepository interface --------------------------------------------

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        return await self.add_decision(entity)

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        return await self.get_decision(str(entity_id))

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self.list_decisions(filters=filters, skip=skip, limit=limit)

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_decision(str(entity_id))
        if existing is None:
            return None
        existing.update(updates)
        return existing

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query("DELETE FROM decision_records WHERE id = ?", [str(entity_id)])
        return bool(result)

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self.count_decisions(filters=filters)

    # -- decisions -----------------------------------------------------------

    async def add_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        # Pack entity_id/entity_type into input_summary and data_sources_used
        input_data = decision.get("input_summary", {})
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except (json.JSONDecodeError, TypeError):
                input_data = {"raw": input_data}
        input_data.setdefault("entity_id", decision.get("entity_id", ""))
        input_data.setdefault("entity_type", decision.get("entity_type", ""))

        data_sources = {
            "entity_id": decision.get("entity_id", ""),
            "entity_type": decision.get("entity_type", ""),
        }

        human_oversight = json.dumps(
            {
                "human_override": bool(decision.get("human_override", False)),
                "override_reason": decision.get("override_reason"),
            }
        )

        await self.db.execute_query(
            """INSERT INTO decision_records
               (id, agent_id, model_used, model_version, decision_type,
                input_summary, data_sources_used, output_data, reasoning,
                confidence, human_oversight, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                decision["id"],
                decision.get("model_id", decision.get("agent_id", "")),
                decision.get("model_id", ""),
                decision.get("model_version", ""),
                decision.get("decision_type"),
                json.dumps(input_data),
                json.dumps(data_sources),
                json.dumps(decision.get("output_summary", {})),
                decision.get("explanation", ""),
                decision.get("confidence"),
                human_oversight,
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
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM decision_records"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "decision_type" in filters:
                where_clauses.append("decision_type = ?")
                params.append(filters["decision_type"])
            if "entity_type" in filters:
                where_clauses.append("JSON_VALUE(data_sources_used, '$.entity_type') = ?")
                params.append(filters["entity_type"])
            if "entity_id" in filters:
                where_clauses.append("JSON_VALUE(data_sources_used, '$.entity_id') = ?")
                params.append(filters["entity_id"])
        if where_clauses:
            clause = " WHERE " + " AND ".join(where_clauses)
            query += clause

        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_deserialize_decision(r) for r in rows]

    async def count_decisions(self, filters: dict[str, Any] | None = None) -> int:
        count_query = "SELECT COUNT(*) as cnt FROM decision_records"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "decision_type" in filters:
                where_clauses.append("decision_type = ?")
                params.append(filters["decision_type"])
            if "entity_type" in filters:
                where_clauses.append("JSON_VALUE(data_sources_used, '$.entity_type') = ?")
                params.append(filters["entity_type"])
            if "entity_id" in filters:
                where_clauses.append("JSON_VALUE(data_sources_used, '$.entity_id') = ?")
                params.append(filters["entity_id"])
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)
        count_result = await self.db.fetch_one(count_query, params)
        return count_result.get("cnt", 0) if count_result else 0

    # -- audit events --------------------------------------------------------

    async def add_audit_event(self, event: dict[str, Any]) -> dict[str, Any]:
        await self.db.execute_query(
            """INSERT INTO audit_events (id, event_type, actor_type, actor_id, action,
               resource_type, resource_id, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                event["id"],
                event.get("action", ""),
                "agent" if "agent" in event.get("actor", "") else "system",
                event.get("actor", ""),
                event.get("action", ""),
                event.get("entity_type", ""),
                event.get("entity_id", ""),
                json.dumps(event.get("details", {})),
                event.get("timestamp", event.get("created_at", "")),
            ],
        )
        return event

    async def list_audit_events(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM audit_events"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "entity_type" in filters:
                where_clauses.append("resource_type = ?")
                params.append(filters["entity_type"])
            if "entity_id" in filters:
                where_clauses.append("resource_id = ?")
                params.append(filters["entity_id"])
            if "actor" in filters:
                where_clauses.append("actor_id = ?")
                params.append(filters["actor"])
            if "action" in filters:
                where_clauses.append("action = ?")
                params.append(filters["action"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_deserialize_audit_event(r) for r in rows]

    async def count_audit_events(self, filters: dict[str, Any] | None = None) -> int:
        count_query = "SELECT COUNT(*) as cnt FROM audit_events"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "entity_type" in filters:
                where_clauses.append("resource_type = ?")
                params.append(filters["entity_type"])
            if "entity_id" in filters:
                where_clauses.append("resource_id = ?")
                params.append(filters["entity_id"])
            if "actor" in filters:
                where_clauses.append("actor_id = ?")
                params.append(filters["actor"])
            if "action" in filters:
                where_clauses.append("action = ?")
                params.append(filters["action"])
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)
        count_result = await self.db.fetch_one(count_query, params)
        return count_result.get("cnt", 0) if count_result else 0

    async def clear_audit_events(self) -> None:
        await self.db.execute_query("DELETE FROM audit_events")

    # -- agent-level persistence (wired from agents.base → Foundry flow) ------

    async def store_decision(self, record: dict[str, Any]) -> str:
        """Persist an agent DecisionRecord to the decision_records table."""
        record_id = str(record.get("decision_id", record.get("id", "")))

        entity_id = record.get("entity_id", record.get("agent_id", ""))
        entity_type = record.get("entity_type", "agent")

        input_data = record.get("input_summary", {})
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except (json.JSONDecodeError, TypeError):
                input_data = {"raw": input_data}
        input_data.setdefault("entity_id", entity_id)
        input_data.setdefault("entity_type", entity_type)

        data_sources = {"entity_id": entity_id, "entity_type": entity_type}

        output = record.get("output", record.get("output_summary", {}))
        reasoning = record.get("reasoning", "")
        if isinstance(reasoning, dict):
            reasoning = json.dumps(reasoning)

        human_oversight = json.dumps(
            {
                "human_override": bool(record.get("human_override", False)),
                "override_reason": record.get("override_reason"),
                "level": record.get("human_oversight", "recommended"),
            }
        )

        await self.db.execute_query(
            """INSERT INTO decision_records
               (id, agent_id, model_used, model_version, decision_type,
                input_summary, data_sources_used, output_data, reasoning,
                confidence, human_oversight, execution_time_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                record_id,
                record.get("agent_id", record.get("model_used", "")),
                record.get("model_used", record.get("model_id", "")),
                record.get("model_version", ""),
                record.get("decision_type"),
                json.dumps(input_data),
                json.dumps(data_sources),
                json.dumps(output),
                reasoning,
                record.get("confidence", 0),
                human_oversight,
                record.get("execution_time_ms"),
                record.get("created_at", record.get("timestamp", "")),
            ],
        )
        return record_id

    async def store_audit_event(self, event: dict[str, Any]) -> str:
        """Persist an audit event from the agent workflow."""
        from uuid import uuid4

        event_id = str(event.get("id", uuid4()))
        actor = event.get("actor", event.get("actor_id", "agent"))
        await self.db.execute_query(
            """INSERT INTO audit_events (id, event_type, actor_type, actor_id, action,
               resource_type, resource_id, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                event_id,
                event.get("action", ""),
                "agent" if "agent" in actor else "system",
                actor,
                event.get("action", ""),
                event.get("entity_type", event.get("resource_type", "")),
                event.get("entity_id", event.get("resource_id", "")),
                json.dumps(event.get("details", {})),
                event.get("timestamp", event.get("created_at", "")),
            ],
        )
        return event_id


def _deserialize_decision(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL decision_records columns back to API-level field names."""
    # Parse JSON columns
    for col in ("input_summary", "output_data", "data_sources_used", "human_oversight", "fairness_metrics"):
        if col in row and isinstance(row[col], str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                row[col] = json.loads(row[col])

    # Extract entity_id / entity_type from data_sources_used or input_summary
    ds = row.pop("data_sources_used", None) or {}
    if isinstance(ds, str):
        ds = {}
    inp = row.get("input_summary", {})
    if isinstance(inp, str):
        try:
            inp = json.loads(inp)
            row["input_summary"] = inp
        except (json.JSONDecodeError, TypeError):
            inp = {}

    row["entity_id"] = ds.get("entity_id") or (inp.get("entity_id") if isinstance(inp, dict) else "") or ""
    row["entity_type"] = ds.get("entity_type") or (inp.get("entity_type") if isinstance(inp, dict) else "") or ""

    # Map model_used / agent_id → model_id
    raw_agent_id = row.get("agent_id", "")
    row["model_id"] = row.pop("model_used", "") or raw_agent_id
    row.pop("agent_id", None)

    # Derive human-readable agent_name for the compliance dashboard
    _agent_display = {
        "openinsure-submission": "Submission Triage Agent",
        "openinsure-underwriting": "Underwriting Agent",
        "openinsure-policy": "Policy Review Agent",
        "openinsure-orchestrator": "Orchestrator Agent",
        "openinsure-claims": "Claims Assessment Agent",
        "triage-agent-v1": "Submission Triage Agent",
        "underwriting-agent-v1": "Underwriting Agent",
        "fraud-detection-v1": "Claims Fraud Detection",
        "rating-engine-v1": "Rating Engine",
        "gpt-5.1": "Foundry GPT-5.1",
    }
    _aid = raw_agent_id or row.get("model_id", "")
    row["agent_name"] = _agent_display.get(
        _aid, _aid.replace("-", " ").replace("_", " ").title() if _aid else "Unknown Agent"
    )

    # Map output_data → output_summary
    row["output_summary"] = row.pop("output_data", {}) or {}

    # Map reasoning → explanation
    reasoning = row.pop("reasoning", "")
    row["explanation"] = reasoning if isinstance(reasoning, str) else json.dumps(reasoning) if reasoning else ""

    # Parse human_oversight → human_override + override_reason
    oversight = row.pop("human_oversight", None)
    if isinstance(oversight, dict):
        row["human_override"] = bool(oversight.get("human_override", False))
        row["override_reason"] = oversight.get("override_reason")
    elif isinstance(oversight, str):
        row["human_override"] = "true" in oversight.lower() if oversight else False
        row["override_reason"] = None
    else:
        row["human_override"] = False
        row["override_reason"] = None

    # Normalise created_at to ISO string
    if "created_at" in row and hasattr(row["created_at"], "isoformat"):
        row["created_at"] = row["created_at"].isoformat()
    elif "created_at" in row:
        row["created_at"] = str(row["created_at"]) if row["created_at"] else ""

    # Remove DB-only columns not expected by the API model
    for col in ("agent_version", "knowledge_graph_queries", "fairness_metrics", "error_message"):
        row.pop(col, None)
    # Keep execution_time_ms — used by the agent-traces endpoint

    return row


def _deserialize_audit_event(row: dict[str, Any]) -> dict[str, Any]:
    if "details" in row and isinstance(row["details"], str):
        row["details"] = json.loads(row["details"])
    # Map SQL column names to API field names
    if "resource_type" in row and "entity_type" not in row:
        row["entity_type"] = row.pop("resource_type")
    if "resource_id" in row and "entity_id" not in row:
        row["entity_id"] = row.pop("resource_id")
    if "actor_id" in row and "actor" not in row:
        row["actor"] = row.pop("actor_id")
    if "created_at" in row and "timestamp" not in row:
        val = row.pop("created_at")
        row["timestamp"] = val.isoformat() if hasattr(val, "isoformat") else str(val) if val else ""
    # Remove SQL-only columns not expected by API
    row.pop("actor_type", None)
    row.pop("event_type", None)
    row.pop("correlation_id", None)
    return row
