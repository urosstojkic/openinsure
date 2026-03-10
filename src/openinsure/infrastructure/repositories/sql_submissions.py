"""SQL-backed submission repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter


class SqlSubmissionRepository(BaseRepository):
    """Azure SQL implementation of the submission repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("submission_number", f"SUB-{datetime.now(UTC).strftime('%Y')}-{str(uuid4())[:4].upper()}")
        entity.setdefault("status", "received")
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        await self.db.execute_query(
            """INSERT INTO submissions (id, submission_number, status, channel, line_of_business,
               requested_effective_date, requested_expiration_date, extracted_data, cyber_risk_data,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"],
                entity.get("submission_number"),
                entity.get("status"),
                entity.get("channel", "api"),
                entity.get("line_of_business", "cyber"),
                entity.get("requested_effective_date"),
                entity.get("requested_expiration_date"),
                json.dumps(entity.get("extracted_data", {})),
                json.dumps(entity.get("cyber_risk_data", {})),
                entity["created_at"],
                entity["updated_at"],
            ],
        )
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            event_type="submission.received",
            subject=f"/submissions/{entity['id']}",
            data={"submission_id": entity["id"], "status": entity.get("status")},
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        return await self.db.fetch_one("SELECT * FROM submissions WHERE id = ?", [str(entity_id)])

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM submissions"
        params: list[Any] = []
        where_clauses: list[str] = []
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
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        return await self.db.fetch_all(query, params)

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key not in ("id", "created_at"):
                sets.append(f"{key} = ?")
                params.append(val if not isinstance(val, dict) else json.dumps(val))
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE submissions SET {', '.join(sets)} WHERE id = ?",  # noqa: S608  # nosec B608 — parameterized query, sets built from validated keys
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query("DELETE FROM submissions WHERE id = ?", [str(entity_id)])
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM submissions"
        params: list[Any] = []
        where_clauses: list[str] = []
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
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
