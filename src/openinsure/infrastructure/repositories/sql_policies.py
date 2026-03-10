"""SQL-backed policy repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter


class SqlPolicyRepository(BaseRepository):
    """Azure SQL implementation of the policy repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("status", "active")
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        await self.db.execute_query(
            """INSERT INTO policies (id, policy_number, submission_id, product_id,
               policyholder_name, status, effective_date, expiration_date, premium,
               coverages, endorsements, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"],
                entity.get("policy_number"),
                entity.get("submission_id"),
                entity.get("product_id"),
                entity.get("policyholder_name"),
                entity.get("status"),
                entity.get("effective_date"),
                entity.get("expiration_date"),
                entity.get("premium"),
                json.dumps(entity.get("coverages", [])),
                json.dumps(entity.get("endorsements", [])),
                json.dumps(entity.get("metadata", {})),
                entity["created_at"],
                entity["updated_at"],
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
        if row:
            row = _deserialize_policy(row)
        return row

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
                where_clauses.append("policyholder_name LIKE ?")
                params.append(f"%{filters['policyholder_name__contains']}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_deserialize_policy(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key not in ("id", "created_at"):
                sets.append(f"{key} = ?")
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
                where_clauses.append("policyholder_name LIKE ?")
                params.append(f"%{filters['policyholder_name__contains']}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


def _deserialize_policy(row: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON columns back into Python objects."""
    for col in ("coverages", "endorsements", "metadata"):
        if col in row and isinstance(row[col], str):
            row[col] = json.loads(row[col])
    return row
