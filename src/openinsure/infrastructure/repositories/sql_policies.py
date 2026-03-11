"""SQL-backed policy repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

# -- key mapping between API entity dicts and SQL columns -------------------

_POLICY_API_TO_SQL_KEY: dict[str, str] = {
    "policyholder_name": "insured_id",
    "premium": "total_premium",
}

_POLICY_SKIP_IN_SQL: set[str] = {"coverages", "endorsements", "metadata", "documents"}


def _policy_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API policy dict keys to SQL column names for INSERT."""
    return {
        "id": entity.get("id"),
        "policy_number": entity.get("policy_number"),
        "status": entity.get("status", "active"),
        "product_id": entity.get("product_id"),
        "submission_id": entity.get("submission_id"),
        "insured_id": None  # FK to parties — NULL until party created,
        "effective_date": entity.get("effective_date"),
        "expiration_date": entity.get("expiration_date"),
        "total_premium": entity.get("premium", entity.get("total_premium")),
        "written_premium": entity.get("written_premium"),
        "earned_premium": entity.get("earned_premium"),
        "unearned_premium": entity.get("unearned_premium"),
        "bound_at": entity.get("bound_at"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _policy_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API policy dict keys."""
    premium = float(row["total_premium"]) if row.get("total_premium") else None
    return {
        "id": str(row.get("id", "")),
        "policy_number": row.get("policy_number", ""),
        "policyholder_name": ""  # Stored in entity metadata, not insured_id FK,
        "status": row.get("status", "active"),
        "product_id": row.get("product_id", ""),
        "submission_id": str(row.get("submission_id", "")),
        "effective_date": str(row.get("effective_date", "")),
        "expiration_date": str(row.get("expiration_date", "")),
        "premium": premium,
        "total_premium": premium,
        "written_premium": float(row["written_premium"]) if row.get("written_premium") else None,
        "earned_premium": float(row["earned_premium"]) if row.get("earned_premium") else None,
        "unearned_premium": float(row["unearned_premium"]) if row.get("unearned_premium") else None,
        "coverages": [],
        "endorsements": [],
        "metadata": {},
        "documents": [],
        "bound_at": str(row.get("bound_at", "")) if row.get("bound_at") else None,
        "created_at": str(row.get("created_at", "")),
        "updated_at": str(row.get("updated_at", "")),
    }


class SqlPolicyRepository(BaseRepository):
    """Azure SQL implementation of the policy repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("status", "active")
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        row = _policy_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO policies (id, policy_number, status, product_id, submission_id,
               insured_id, effective_date, expiration_date, total_premium,
               written_premium, earned_premium, unearned_premium, bound_at,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["policy_number"],
                row["status"],
                row["product_id"],
                row["submission_id"],
                row["insured_id"],
                row["effective_date"],
                row["expiration_date"],
                row["total_premium"],
                row["written_premium"],
                row["earned_premium"],
                row["unearned_premium"],
                row["bound_at"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            event_type="policy.bound",
            subject=f"/policies/{entity['id']}",
            data={"policy_id": entity["id"], "status": entity.get("status")},
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM policies WHERE id = ?", [str(entity_id)])
        return _policy_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM policies"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "product_id" in filters:
                where_clauses.append("product_id = ?")
                params.append(filters["product_id"])
            if "policyholder_name__contains" in filters:
                where_clauses.append("insured_id LIKE ?")
                params.append(f"%{filters['policyholder_name__contains']}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_policy_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        from openinsure.domain.state_machine import (
            validate_policy_invariants,
            validate_policy_transition,
        )

        existing = await self.get_by_id(entity_id)
        if "status" in updates and existing and existing.get("status"):
            validate_policy_transition(existing["status"], updates["status"])
        merged = {**(existing or {}), **updates}
        validate_policy_invariants(merged)

        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at") or key in _POLICY_SKIP_IN_SQL:
                continue
            col = _POLICY_API_TO_SQL_KEY.get(key, key)
            sets.append(f"{col} = ?")
            params.append(val if not isinstance(val, (dict, list)) else json.dumps(val))
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE policies SET {', '.join(sets)} WHERE id = ?",  # noqa: S608  # nosec B608 — parameterized query, sets built from validated keys
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query("DELETE FROM policies WHERE id = ?", [str(entity_id)])
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM policies"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "product_id" in filters:
                where_clauses.append("product_id = ?")
                params.append(filters["product_id"])
            if "policyholder_name__contains" in filters:
                where_clauses.append("insured_id LIKE ?")
                params.append(f"%{filters['policyholder_name__contains']}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0

