"""SQL-backed submission repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import (
    BaseRepository,
    IntegrityConstraintError,
    safe_pagination_clause,
)

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter, TransactionContext

# -- key mapping between API entity dicts and SQL columns -------------------

_API_TO_SQL_KEY: dict[str, str] = {
    "applicant_name": "applicant_id",
    "risk_data": "cyber_risk_data",
    "metadata": "extracted_data",
}

_SKIP_IN_SQL: set[str] = {
    "applicant_email",
    "documents",
    "lob",
    "received_date",
    "company_name",
    "risk_score",
    "priority",
    "assigned_to",
    "decision_history",
    "row_version",
}

# The SQL CHECK constraint uses 'broker_platform', but the API enum uses 'broker'.
_CHANNEL_API_TO_SQL: dict[str, str] = {"broker": "broker_platform"}
_CHANNEL_SQL_TO_API: dict[str, str] = {"broker_platform": "broker"}


def _api_channel_to_sql(channel: str) -> str:
    """Map API channel enum value to the SQL CHECK-constrained value."""
    return _CHANNEL_API_TO_SQL.get(channel, channel)


def _sql_channel_to_api(channel: str) -> str:
    """Map SQL channel value back to the API enum value."""
    return _CHANNEL_SQL_TO_API.get(channel, channel)


def _to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API entity keys to SQL column names for INSERT."""
    # Store applicant_name inside extracted_data JSON since applicant_id
    # is a UNIQUEIDENTIFIER FK, not a text field.
    metadata = dict(entity.get("metadata", {}))
    metadata["applicant_name"] = entity.get("applicant_name", "")
    metadata["applicant_email"] = entity.get("applicant_email", "")

    return {
        "id": entity.get("id"),
        "submission_number": entity.get("submission_number"),
        "status": entity.get("status", "received"),
        "channel": _api_channel_to_sql(entity.get("channel", "api")),
        "line_of_business": entity.get("line_of_business", "cyber"),
        "applicant_id": None,  # FK to parties table — NULL until party is created
        "requested_effective_date": entity.get("requested_effective_date"),
        "requested_expiration_date": entity.get("requested_expiration_date"),
        "extracted_data": json.dumps(metadata),
        "cyber_risk_data": json.dumps(entity.get("risk_data", entity.get("cyber_risk_data", {}))),
        "triage_result": json.dumps(entity.get("triage_result", {})) if entity.get("triage_result") else None,
        "quoted_premium": entity.get("quoted_premium"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API entity keys.

    Ensures every value is properly typed — no None where str is expected.
    """

    def _str(val: Any) -> str:
        if val is None:
            return ""
        # Convert SQL datetime objects to ISO 8601 string
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    def _json(val: Any) -> dict[str, Any]:
        if val is None:
            return {}
        if isinstance(val, dict):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}

    metadata = _json(row.get("extracted_data"))

    # Ensure submission_number is human-readable (not a raw UUID)
    sub_num = _str(row.get("submission_number"))
    if sub_num and not sub_num.startswith("SUB-"):
        sub_num = f"SUB-{sub_num[:8].upper()}"

    lob = _str(row.get("line_of_business")) or "cyber"
    created = _str(row.get("created_at"))

    triage = _json(row.get("triage_result")) if row.get("triage_result") else None
    risk_score = float(triage.get("risk_score", 0)) if triage else 0.0

    rv = row.get("row_version")

    return {
        "id": _str(row.get("id")),
        "submission_number": sub_num,
        "applicant_name": metadata.pop("applicant_name", "") if isinstance(metadata, dict) else "",
        "applicant_email": metadata.pop("applicant_email", None) if isinstance(metadata, dict) else None,
        "status": _str(row.get("status")) or "received",
        "channel": _sql_channel_to_api(_str(row.get("channel")) or "api"),
        "line_of_business": lob,
        "lob": lob,
        "risk_data": _json(row.get("cyber_risk_data")),
        "metadata": metadata,
        "documents": [],
        "triage_result": triage,
        "quoted_premium": float(row["quoted_premium"]) if row.get("quoted_premium") else None,
        "requested_effective_date": _str(row.get("requested_effective_date")),
        "requested_expiration_date": _str(row.get("requested_expiration_date")),
        "created_at": created,
        "updated_at": _str(row.get("updated_at")),
        # Dashboard-expected aliases
        "received_date": created,
        "company_name": metadata.get("company_name", "") if isinstance(metadata, dict) else "",
        "risk_score": risk_score,
        "priority": triage.get("priority", "medium") if triage else "medium",
        "assigned_to": triage.get("assigned_to") if triage else None,
        "decision_history": [],
        "row_version": rv.hex() if isinstance(rv, (bytes, bytearray)) else None,
        # Stage timestamps for processing-time metrics
        "received_at": _str(row.get("received_at")),
        "triaged_at": _str(row.get("triaged_at")),
        "quoted_at": _str(row.get("quoted_at")),
        "bound_at": _str(row.get("bound_at")),
        "declined_at": _str(row.get("declined_at")),
    }


class SqlSubmissionRepository(BaseRepository):
    """Azure SQL implementation of the submission repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any], *, txn: TransactionContext | None = None) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("submission_number", f"SUB-{datetime.now(UTC).strftime('%Y')}-{str(uuid4())[:4].upper()}")
        entity.setdefault("status", "received")
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        row = _to_sql_row(entity)
        sql = """INSERT INTO submissions (id, submission_number, status, channel, line_of_business,
               applicant_id, requested_effective_date, requested_expiration_date,
               extracted_data, cyber_risk_data, triage_result, quoted_premium,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = [
            row["id"],
            row["submission_number"],
            row["status"],
            row["channel"],
            row["line_of_business"],
            row["applicant_id"],
            row["requested_effective_date"],
            row["requested_expiration_date"],
            row["extracted_data"],
            row["cyber_risk_data"],
            row["triage_result"],
            row["quoted_premium"],
            row["created_at"],
            row["updated_at"],
        ]
        if txn:
            await txn.async_execute_query(sql, params)
        else:
            await self.db.execute_query(sql, params)
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            event_type="submission.received",
            subject=f"/submissions/{entity['id']}",
            data={"submission_id": entity["id"], "status": entity.get("status")},
        )
        # Return the entity with all fields populated for the response model
        entity.setdefault("applicant_name", entity.get("applicant_name", ""))
        entity.setdefault("applicant_email", None)
        entity.setdefault("risk_data", entity.get("risk_data", entity.get("cyber_risk_data", {})))
        entity.setdefault("metadata", entity.get("metadata", {}))
        entity.setdefault("documents", [])
        entity.setdefault("channel", "api")
        entity.setdefault("line_of_business", "cyber")
        return entity

    async def get_by_id(self, entity_id: UUID | str, *, include_deleted: bool = False) -> dict[str, Any] | None:
        sql = "SELECT * FROM submissions WHERE id = ?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        row = await self.db.fetch_one(sql, [str(entity_id)])
        return _from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM submissions"
        params: list[Any] = []
        where_clauses: list[str] = ["deleted_at IS NULL"]
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "line_of_business" in filters:
                where_clauses.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "channel" in filters:
                where_clauses.append("channel = ?")
                params.append(filters["channel"])
        query += " WHERE " + " AND ".join(where_clauses)
        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_from_sql_row(r) for r in rows]

    async def update(
        self,
        entity_id: UUID | str,
        updates: dict[str, Any],
        *,
        txn: TransactionContext | None = None,
        expected_version: str | None = None,
    ) -> dict[str, Any] | None:
        from openinsure.domain.state_machine import (
            validate_submission_invariants,
            validate_submission_transition,
        )

        if "status" in updates:
            existing = await self.get_by_id(entity_id)
            if existing and existing.get("status"):
                validate_submission_transition(existing["status"], updates["status"])
            merged = {**(existing or {}), **updates}
            validate_submission_invariants(merged)

        sets: list[str] = []
        params: list[Any] = []
        seen_cols: set[str] = set()
        for key, val in updates.items():
            if key in ("id", "created_at", "updated_at") or key in _SKIP_IN_SQL:
                continue
            col = _API_TO_SQL_KEY.get(key, key)
            if col in seen_cols:
                continue  # Prevent duplicate SET clause
            seen_cols.add(col)
            sets.append(f"{col} = ?")
            params.append(val if not isinstance(val, (dict, list)) else json.dumps(val))
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        where = "WHERE id = ?"
        if expected_version:
            where += " AND row_version = CONVERT(BINARY(8), ?, 1)"
            params.append(f"0x{expected_version}")
        sql = f"UPDATE submissions SET {', '.join(sets)} {where}"  # noqa: S608  # nosec B608 — parameterized query, sets built from validated keys
        if txn:
            rowcount = await txn.async_execute_query(sql, params)
        else:
            rowcount = await self.db.execute_query(sql, params)
        if expected_version and rowcount == 0:
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="Record modified by another user")
        if txn:
            return None
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        try:
            result = await self.db.execute_query(
                "UPDATE submissions SET deleted_at = GETUTCDATE() WHERE id = ? AND deleted_at IS NULL",
                [str(entity_id)],
            )
            return result > 0
        except Exception as exc:
            if "REFERENCE" in str(exc).upper() or "547" in str(exc):
                raise IntegrityConstraintError from exc
            raise

    async def restore(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "UPDATE submissions SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            [str(entity_id)],
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM submissions"
        params: list[Any] = []
        where_clauses: list[str] = ["deleted_at IS NULL"]
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "line_of_business" in filters:
                where_clauses.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "channel" in filters:
                where_clauses.append("channel = ?")
                params.append(filters["channel"])
        query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
