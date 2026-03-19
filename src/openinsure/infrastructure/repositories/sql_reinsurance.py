"""SQL-backed reinsurance repositories using Azure SQL Database.

Provides SQL persistence for treaties, cessions, and recoveries.  Mirrors
the ``InMemoryReinsuranceRepository`` interface so the factory can swap
implementations based on ``storage_mode``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------


def _treaty_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API treaty dict keys to SQL column names."""
    lob = entity.get("lines_of_business", [])
    return {
        "id": entity.get("id"),
        "treaty_number": entity.get("treaty_number"),
        "treaty_type": entity.get("treaty_type"),
        "reinsurer_name": entity.get("reinsurer_name"),
        "status": entity.get("status", "active"),
        "effective_date": entity.get("effective_date"),
        "expiration_date": entity.get("expiration_date"),
        "lines_of_business": json.dumps(lob) if isinstance(lob, list) else lob,
        "retention": entity.get("retention", 0),
        "treaty_limit": entity.get("limit", 0),
        "rate": entity.get("rate", 0),
        "capacity_total": entity.get("capacity_total", 0),
        "capacity_used": entity.get("capacity_used", 0),
        "reinstatements": entity.get("reinstatements", 0),
        "description": entity.get("description", ""),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _treaty_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API treaty dict keys."""

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
        "treaty_number": _str(row.get("treaty_number")),
        "treaty_type": _str(row.get("treaty_type")),
        "reinsurer_name": _str(row.get("reinsurer_name")),
        "status": _str(row.get("status")) or "active",
        "effective_date": _str(row.get("effective_date")),
        "expiration_date": _str(row.get("expiration_date")),
        "lines_of_business": _json_list(row.get("lines_of_business")),
        "retention": float(row.get("retention") or 0),
        "limit": float(row.get("treaty_limit") or 0),
        "rate": float(row.get("rate") or 0),
        "capacity_total": float(row.get("capacity_total") or 0),
        "capacity_used": float(row.get("capacity_used") or 0),
        "reinstatements": int(row.get("reinstatements") or 0),
        "description": _str(row.get("description")),
        "created_at": _str(row.get("created_at")),
        "updated_at": _str(row.get("updated_at")),
    }


def _cession_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL cession row to API dict."""

    def _str(val: Any) -> str:
        if val is None:
            return ""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return {
        "id": _str(row.get("id")),
        "treaty_id": _str(row.get("treaty_id")),
        "policy_id": _str(row.get("policy_id")),
        "policy_number": _str(row.get("policy_number")),
        "ceded_premium": float(row.get("ceded_premium") or 0),
        "ceded_limit": float(row.get("ceded_limit") or 0),
        "cession_date": _str(row.get("cession_date")),
        "created_at": _str(row.get("created_at")),
    }


def _recovery_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL recovery row to API dict."""

    def _str(val: Any) -> str:
        if val is None:
            return ""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return {
        "id": _str(row.get("id")),
        "treaty_id": _str(row.get("treaty_id")),
        "claim_id": _str(row.get("claim_id")),
        "claim_number": _str(row.get("claim_number")),
        "recovery_amount": float(row.get("recovery_amount") or 0),
        "recovery_date": _str(row.get("recovery_date")),
        "status": _str(row.get("status")) or "pending",
        "created_at": _str(row.get("created_at")),
    }


# ---------------------------------------------------------------------------
# Treaty repository
# ---------------------------------------------------------------------------


class SqlReinsuranceRepository(BaseRepository):
    """Azure SQL implementation of the treaty repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("treaty_number", f"TRE-{uuid4().hex[:8].upper()}")
        entity.setdefault("status", "active")
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)

        row = _treaty_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO reinsurance_treaties
               (id, treaty_number, treaty_type, reinsurer_name, status,
                effective_date, expiration_date, lines_of_business,
                retention, treaty_limit, rate, capacity_total, capacity_used,
                reinstatements, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"], row["treaty_number"], row["treaty_type"],
                row["reinsurer_name"], row["status"],
                row["effective_date"], row["expiration_date"],
                row["lines_of_business"],
                row["retention"], row["treaty_limit"], row["rate"],
                row["capacity_total"], row["capacity_used"],
                row["reinstatements"], row["description"],
                row["created_at"], row["updated_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM reinsurance_treaties WHERE id = ?", [str(entity_id)]
        )
        return _treaty_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM reinsurance_treaties"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            for key in ("status", "treaty_type", "reinsurer_name"):
                if key in filters:
                    where.append(f"{key} = ?")
                    params.append(filters[key])
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_treaty_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        skip_keys = {"id", "created_at", "treaty_number"}
        col_map = {"limit": "treaty_limit", "lines_of_business": "lines_of_business"}
        for key, val in updates.items():
            if key in skip_keys:
                continue
            col = col_map.get(key, key)
            if key == "lines_of_business" and isinstance(val, list):
                val = json.dumps(val)  # noqa: PLW2901
            sets.append(f"{col} = ?")
            params.append(val)
        if not sets:
            return await self.get_by_id(entity_id)
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE reinsurance_treaties SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM reinsurance_treaties WHERE id = ?", [str(entity_id)]
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM reinsurance_treaties"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            for key in ("status", "treaty_type", "reinsurer_name"):
                if key in filters:
                    where.append(f"{key} = ?")
                    params.append(filters[key])
        if where:
            query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


# ---------------------------------------------------------------------------
# Cession repository
# ---------------------------------------------------------------------------


class SqlCessionRepository(BaseRepository):
    """Azure SQL implementation of the cession repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("created_at", now)
        await self.db.execute_query(
            """INSERT INTO reinsurance_cessions
               (id, treaty_id, policy_id, policy_number,
                ceded_premium, ceded_limit, cession_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"], entity["treaty_id"], entity["policy_id"],
                entity["policy_number"], entity["ceded_premium"],
                entity["ceded_limit"], entity["cession_date"],
                entity["created_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM reinsurance_cessions WHERE id = ?", [str(entity_id)]
        )
        return _cession_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM reinsurance_cessions"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            for key in ("treaty_id", "policy_id"):
                if key in filters:
                    where.append(f"{key} = ?")
                    params.append(filters[key])
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_cession_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        # Cessions are generally immutable; allow status-like updates if needed
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM reinsurance_cessions WHERE id = ?", [str(entity_id)]
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM reinsurance_cessions"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            for key in ("treaty_id", "policy_id"):
                if key in filters:
                    where.append(f"{key} = ?")
                    params.append(filters[key])
        if where:
            query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


# ---------------------------------------------------------------------------
# Recovery repository
# ---------------------------------------------------------------------------


class SqlRecoveryRepository(BaseRepository):
    """Azure SQL implementation of the recovery repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("created_at", now)
        await self.db.execute_query(
            """INSERT INTO reinsurance_recoveries
               (id, treaty_id, claim_id, claim_number,
                recovery_amount, recovery_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"], entity["treaty_id"], entity["claim_id"],
                entity["claim_number"], entity["recovery_amount"],
                entity["recovery_date"], entity.get("status", "pending"),
                entity["created_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM reinsurance_recoveries WHERE id = ?", [str(entity_id)]
        )
        return _recovery_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM reinsurance_recoveries"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            for key in ("treaty_id", "claim_id", "status"):
                if key in filters:
                    where.append(f"{key} = ?")
                    params.append(filters[key])
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_recovery_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at"):
                continue
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return await self.get_by_id(entity_id)
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE reinsurance_recoveries SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM reinsurance_recoveries WHERE id = ?", [str(entity_id)]
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM reinsurance_recoveries"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            for key in ("treaty_id", "claim_id", "status"):
                if key in filters:
                    where.append(f"{key} = ?")
                    params.append(filters[key])
        if where:
            query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
