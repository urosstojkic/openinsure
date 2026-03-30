"""SQL-backed renewal record repository using Azure SQL Database."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import (
    BaseRepository,
    IntegrityConstraintError,
    safe_pagination_clause,
)

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

logger = logging.getLogger(__name__)


def _safe_uuid(val: Any) -> str | None:
    if val is None:
        return None
    try:
        return str(UUID(str(val)))
    except (ValueError, AttributeError):
        return None


def _renewal_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API renewal dict to SQL column values for INSERT."""
    conditions = entity.get("conditions", [])
    if isinstance(conditions, list):
        conditions = json.dumps(conditions)
    return {
        "id": entity.get("id"),
        "original_policy_id": _safe_uuid(entity.get("original_policy_id")),
        "renewal_policy_id": _safe_uuid(entity.get("renewal_policy_id")),
        "status": entity.get("status", "pending"),
        "expiring_premium": entity.get("expiring_premium"),
        "renewal_premium": entity.get("renewal_premium"),
        "rate_change_pct": entity.get("rate_change_pct"),
        "recommendation": entity.get("recommendation", "review_required"),
        "conditions": conditions,
        "generated_by": entity.get("generated_by", "system"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _renewal_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL row back to API renewal dict."""

    def _str(val: Any) -> str:
        if val is None:
            return ""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    def _json_list(val: Any) -> list[str]:
        if val is None:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    return {
        "id": _str(row.get("id")),
        "original_policy_id": _str(row.get("original_policy_id")),
        "renewal_policy_id": _str(row.get("renewal_policy_id")) or None,
        "status": _str(row.get("status")) or "pending",
        "expiring_premium": float(row["expiring_premium"]) if row.get("expiring_premium") else 0,
        "renewal_premium": float(row["renewal_premium"]) if row.get("renewal_premium") else 0,
        "rate_change_pct": float(row["rate_change_pct"]) if row.get("rate_change_pct") else 0,
        "recommendation": _str(row.get("recommendation")) or "review_required",
        "conditions": _json_list(row.get("conditions")),
        "generated_by": _str(row.get("generated_by")) or "system",
        "created_at": _str(row.get("created_at")),
        "updated_at": _str(row.get("updated_at")),
    }


class SqlRenewalRepository(BaseRepository):
    """Azure SQL implementation of the renewal record repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("status", "pending")
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)

        row = _renewal_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO renewal_records
               (id, original_policy_id, renewal_policy_id, status,
                expiring_premium, renewal_premium, rate_change_pct,
                recommendation, conditions, generated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["original_policy_id"],
                row["renewal_policy_id"],
                row["status"],
                row["expiring_premium"],
                row["renewal_premium"],
                row["rate_change_pct"],
                row["recommendation"],
                row["conditions"],
                row["generated_by"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        try:
            from openinsure.services.event_publisher import publish_domain_event

            await publish_domain_event(
                event_type="renewal.created",
                subject=f"/renewals/{entity['id']}",
                data={"renewal_id": entity["id"], "status": entity.get("status")},
            )
        except Exception:
            logger.warning("Failed to publish renewal.created event for %s", entity["id"])
        return entity

    async def get_by_id(self, entity_id: UUID | str, *, include_deleted: bool = False) -> dict[str, Any] | None:
        sql = "SELECT * FROM renewal_records WHERE id = ?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        row = await self.db.fetch_one(sql, [str(entity_id)])
        return _renewal_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM renewal_records"
        params: list[Any] = []
        where_clauses: list[str] = ["deleted_at IS NULL"]
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "original_policy_id" in filters:
                where_clauses.append("original_policy_id = ?")
                params.append(filters["original_policy_id"])
        query += " WHERE " + " AND ".join(where_clauses)
        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_renewal_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_by_id(entity_id)
        if existing is None:
            return None

        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at", "updated_at"):
                continue
            if key == "conditions" and isinstance(val, list):
                val = json.dumps(val)  # noqa: PLW2901
            sets.append(f"{key} = ?")
            params.append(val)
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE renewal_records SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        try:
            result = await self.db.execute_query(
                "UPDATE renewal_records SET deleted_at = GETUTCDATE() WHERE id = ? AND deleted_at IS NULL",
                [str(entity_id)],
            )
            return result > 0
        except Exception as exc:
            if "REFERENCE" in str(exc).upper() or "547" in str(exc):
                raise IntegrityConstraintError from exc
            raise

    async def restore(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "UPDATE renewal_records SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            [str(entity_id)],
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM renewal_records"
        params: list[Any] = []
        where_clauses: list[str] = ["deleted_at IS NULL"]
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "original_policy_id" in filters:
                where_clauses.append("original_policy_id = ?")
                params.append(filters["original_policy_id"])
        query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
