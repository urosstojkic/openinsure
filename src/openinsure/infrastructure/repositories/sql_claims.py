"""SQL-backed claims repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter


class SqlClaimRepository(BaseRepository):
    """Azure SQL implementation of the claim repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("status", "reported")
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        await self.db.execute_query(
            """INSERT INTO claims (id, claim_number, policy_id, claim_type, status,
               description, date_of_loss, reported_by, contact_email, contact_phone,
               reserves, payments, total_reserved, total_paid, metadata,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"],
                entity.get("claim_number"),
                entity.get("policy_id"),
                entity.get("claim_type"),
                entity.get("status"),
                entity.get("description"),
                entity.get("date_of_loss"),
                entity.get("reported_by"),
                entity.get("contact_email"),
                entity.get("contact_phone"),
                json.dumps(entity.get("reserves", [])),
                json.dumps(entity.get("payments", [])),
                entity.get("total_reserved", 0.0),
                entity.get("total_paid", 0.0),
                json.dumps(entity.get("metadata", {})),
                entity["created_at"],
                entity["updated_at"],
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
        if row:
            row = _deserialize_claim(row)
        return row

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
                where_clauses.append("claim_type = ?")
                params.append(filters["claim_type"])
            if "policy_id" in filters:
                where_clauses.append("policy_id = ?")
                params.append(filters["policy_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_deserialize_claim(r) for r in rows]

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
            if key not in ("id", "created_at"):
                sets.append(f"{key} = ?")
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
                where_clauses.append("claim_type = ?")
                params.append(filters["claim_type"])
            if "policy_id" in filters:
                where_clauses.append("policy_id = ?")
                params.append(filters["policy_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


def _deserialize_claim(row: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON columns back into Python objects."""
    for col in ("reserves", "payments", "metadata"):
        if col in row and isinstance(row[col], str):
            row[col] = json.loads(row[col])
    return row
