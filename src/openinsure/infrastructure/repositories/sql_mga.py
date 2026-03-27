"""SQL-backed MGA authority and bordereau repositories using Azure SQL Database."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository, safe_pagination_clause

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MGA Authority
# ---------------------------------------------------------------------------


def _authority_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API authority dict to SQL column values for INSERT."""
    lobs = entity.get("lines_of_business", [])
    if isinstance(lobs, list):
        lobs = json.dumps(lobs)
    return {
        "id": entity.get("id"),
        "mga_id": entity.get("mga_id"),
        "mga_name": entity.get("mga_name"),
        "status": entity.get("status", "active"),
        "effective_date": entity.get("effective_date"),
        "expiration_date": entity.get("expiration_date"),
        "lines_of_business": lobs,
        "premium_authority": entity.get("premium_authority", 0),
        "premium_written": entity.get("premium_written", 0),
        "claims_authority": entity.get("claims_authority", 0),
        "loss_ratio": entity.get("loss_ratio", 0),
        "compliance_score": entity.get("compliance_score", 100),
        "last_audit_date": entity.get("last_audit_date"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _authority_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL row back to API authority dict."""

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
        "mga_id": _str(row.get("mga_id")),
        "mga_name": _str(row.get("mga_name")),
        "status": _str(row.get("status")) or "active",
        "effective_date": _str(row.get("effective_date")),
        "expiration_date": _str(row.get("expiration_date")),
        "lines_of_business": _json_list(row.get("lines_of_business")),
        "premium_authority": float(row["premium_authority"]) if row.get("premium_authority") else 0,
        "premium_written": float(row["premium_written"]) if row.get("premium_written") else 0,
        "claims_authority": float(row["claims_authority"]) if row.get("claims_authority") else 0,
        "loss_ratio": float(row["loss_ratio"]) if row.get("loss_ratio") else 0,
        "compliance_score": int(row["compliance_score"]) if row.get("compliance_score") else 100,
        "last_audit_date": _str(row.get("last_audit_date")) or None,
        "created_at": _str(row.get("created_at")),
        "updated_at": _str(row.get("updated_at")),
    }


class SqlMGAAuthorityRepository(BaseRepository):
    """Azure SQL implementation of the MGA authority repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        # The API layer may set id = mga_id (a human-readable string).
        # The SQL column `id` is UNIQUEIDENTIFIER, so always use a proper UUID.
        entity.setdefault("id", str(uuid4()))
        # If `id` is not a valid UUID (e.g., "mga-001"), generate a real one
        try:
            UUID(str(entity["id"]))
        except (ValueError, AttributeError):
            entity["id"] = str(uuid4())
        entity.setdefault("status", "active")
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)

        row = _authority_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO mga_authorities
               (id, mga_id, mga_name, status, effective_date, expiration_date,
                lines_of_business, premium_authority, premium_written,
                claims_authority, loss_ratio, compliance_score,
                last_audit_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["mga_id"],
                row["mga_name"],
                row["status"],
                row["effective_date"],
                row["expiration_date"],
                row["lines_of_business"],
                row["premium_authority"],
                row["premium_written"],
                row["claims_authority"],
                row["loss_ratio"],
                row["compliance_score"],
                row["last_audit_date"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        # Look up by id or mga_id (mga_id is UNIQUE)
        row = await self.db.fetch_one(
            "SELECT * FROM mga_authorities WHERE id = ? OR mga_id = ?",
            [str(entity_id), str(entity_id)],
        )
        return _authority_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM mga_authorities"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "mga_id" in filters:
                where_clauses.append("mga_id = ?")
                params.append(filters["mga_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_authority_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_by_id(entity_id)
        if existing is None:
            return None

        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at", "updated_at"):
                continue
            if key == "lines_of_business" and isinstance(val, list):
                val = json.dumps(val)  # noqa: PLW2901
            sets.append(f"{key} = ?")
            params.append(val)
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE mga_authorities SET {', '.join(sets)} WHERE id = ? OR mga_id = ?",  # noqa: S608
            [*params, str(entity_id)],
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM mga_authorities WHERE id = ? OR mga_id = ?",
            [str(entity_id), str(entity_id)],
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM mga_authorities"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


# ---------------------------------------------------------------------------
# MGA Bordereau
# ---------------------------------------------------------------------------


def _bordereau_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API bordereau dict to SQL column values for INSERT."""
    exceptions = entity.get("exceptions", [])
    if isinstance(exceptions, list):
        exceptions = json.dumps(exceptions)
    return {
        "id": entity.get("id"),
        "mga_id": entity.get("mga_id"),
        "period": entity.get("period"),
        "premium_reported": entity.get("premium_reported", 0),
        "claims_reported": entity.get("claims_reported", 0),
        "loss_ratio": entity.get("loss_ratio", 0),
        "policy_count": entity.get("policy_count", 0),
        "claim_count": entity.get("claim_count", 0),
        "status": entity.get("status", "pending"),
        "exceptions": exceptions,
        "submitted_at": entity.get("submitted_at") or entity.get("created_at"),
        "validated_at": entity.get("validated_at"),
    }


def _bordereau_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL row back to API bordereau dict."""

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
        "mga_id": _str(row.get("mga_id")),
        "period": _str(row.get("period")),
        "premium_reported": float(row["premium_reported"]) if row.get("premium_reported") else 0,
        "claims_reported": float(row["claims_reported"]) if row.get("claims_reported") else 0,
        "loss_ratio": float(row["loss_ratio"]) if row.get("loss_ratio") else 0,
        "policy_count": int(row["policy_count"]) if row.get("policy_count") else 0,
        "claim_count": int(row["claim_count"]) if row.get("claim_count") else 0,
        "status": _str(row.get("status")) or "pending",
        "exceptions": _json_list(row.get("exceptions")),
        "submitted_at": _str(row.get("submitted_at")),
        "validated_at": _str(row.get("validated_at")) or None,
    }


class SqlMGABordereauRepository(BaseRepository):
    """Azure SQL implementation of the MGA bordereau repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        # Ensure id is a valid UUID for the UNIQUEIDENTIFIER column
        try:
            UUID(str(entity["id"]))
        except (ValueError, AttributeError):
            entity["id"] = str(uuid4())
        entity.setdefault("status", "pending")
        entity.setdefault("submitted_at", now)

        row = _bordereau_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO mga_bordereaux
               (id, mga_id, period, premium_reported, claims_reported,
                loss_ratio, policy_count, claim_count, status,
                exceptions, submitted_at, validated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["mga_id"],
                row["period"],
                row["premium_reported"],
                row["claims_reported"],
                row["loss_ratio"],
                row["policy_count"],
                row["claim_count"],
                row["status"],
                row["exceptions"],
                row["submitted_at"],
                row["validated_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM mga_bordereaux WHERE id = ?",
            [str(entity_id)],
        )
        return _bordereau_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM mga_bordereaux"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "mga_id" in filters:
                where_clauses.append("mga_id = ?")
                params.append(filters["mga_id"])
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        pag_clause, pag_params = safe_pagination_clause("submitted_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_bordereau_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_by_id(entity_id)
        if existing is None:
            return None

        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "submitted_at"):
                continue
            if key == "exceptions" and isinstance(val, list):
                val = json.dumps(val)  # noqa: PLW2901
            sets.append(f"{key} = ?")
            params.append(val)
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE mga_bordereaux SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM mga_bordereaux WHERE id = ?",
            [str(entity_id)],
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM mga_bordereaux"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "mga_id" in filters:
                where_clauses.append("mga_id = ?")
                params.append(filters["mga_id"])
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
