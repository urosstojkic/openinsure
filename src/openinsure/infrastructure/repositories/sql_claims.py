"""SQL-backed claims repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

# -- key mapping between API entity dicts and SQL columns -------------------

_CLAIM_API_TO_SQL_KEY: dict[str, str] = {
    "claim_type": "loss_type",
    "date_of_loss": "loss_date",
}

_CLAIM_SKIP_IN_SQL: set[str] = {
    "reported_by",
    "contact_email",
    "contact_phone",
    "reserves",
    "payments",
    "total_reserved",
    "total_paid",
    "metadata",
}


def _claim_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API claim dict keys to SQL column names for INSERT."""
    return {
        "id": entity.get("id"),
        "claim_number": entity.get("claim_number"),
        "status": entity.get("status", "reported"),
        "policy_id": entity.get("policy_id"),
        "loss_date": entity.get("date_of_loss"),
        "report_date": entity.get("created_at"),
        "loss_type": entity.get("claim_type"),
        "description": entity.get("description"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _claim_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API claim dict keys."""
    return {
        "id": str(row.get("id", "")),
        "claim_number": row.get("claim_number", ""),
        "policy_id": str(row.get("policy_id", "")),
        "claim_type": row.get("loss_type", ""),
        "status": row.get("status", "reported"),
        "description": row.get("description", ""),
        "date_of_loss": str(row.get("loss_date", "")),
        "reported_by": "",
        "contact_email": None,
        "contact_phone": None,
        "reserves": [],
        "payments": [],
        "total_reserved": 0.0,
        "total_paid": 0.0,
        "metadata": {},
        "created_at": str(row.get("created_at", "")),
        "updated_at": str(row.get("updated_at", "")),
    }


class SqlClaimRepository(BaseRepository):
    """Azure SQL implementation of the claim repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("status", "reported")
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        row = _claim_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO claims (id, claim_number, status, policy_id,
               loss_date, report_date, loss_type, description,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["claim_number"],
                row["status"],
                row["policy_id"],
                row["loss_date"],
                row["report_date"],
                row["loss_type"],
                row["description"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            event_type="claim.reported",
            subject=f"/claims/{entity['id']}",
            data={"claim_id": entity["id"], "status": entity.get("status")},
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM claims WHERE id = ?", [str(entity_id)])
        return _claim_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM claims"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "claim_type" in filters:
                where_clauses.append("loss_type = ?")
                params.append(filters["claim_type"])
            if "policy_id" in filters:
                where_clauses.append("policy_id = ?")
                params.append(filters["policy_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_claim_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        from openinsure.domain.state_machine import (
            validate_claim_invariants,
            validate_claim_transition,
        )

        existing = await self.get_by_id(entity_id)
        if "status" in updates and existing and existing.get("status"):
            validate_claim_transition(existing["status"], updates["status"])
        merged = {**(existing or {}), **updates}
        validate_claim_invariants(merged)

        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at") or key in _CLAIM_SKIP_IN_SQL:
                continue
            col = _CLAIM_API_TO_SQL_KEY.get(key, key)
            sets.append(f"{col} = ?")
            params.append(val if not isinstance(val, (dict, list)) else json.dumps(val))
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE claims SET {', '.join(sets)} WHERE id = ?",  # noqa: S608  # nosec B608 — parameterized query, sets built from validated keys
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query("DELETE FROM claims WHERE id = ?", [str(entity_id)])
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM claims"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "claim_type" in filters:
                where_clauses.append("loss_type = ?")
                params.append(filters["claim_type"])
            if "policy_id" in filters:
                where_clauses.append("policy_id = ?")
                params.append(filters["policy_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
