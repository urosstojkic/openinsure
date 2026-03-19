"""SQL-backed actuarial repositories using Azure SQL Database.

Provides SQL persistence for actuarial reserves, loss triangle entries,
and rate adequacy records.
"""

from __future__ import annotations

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


def _str(val: Any) -> str:
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _reserve_from_sql(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _str(row.get("id")),
        "line_of_business": _str(row.get("line_of_business")),
        "accident_year": int(row.get("accident_year") or 0),
        "reserve_type": _str(row.get("reserve_type")),
        "carried_amount": float(row.get("carried_amount") or 0),
        "indicated_amount": float(row.get("indicated_amount") or 0),
        "selected_amount": float(row.get("selected_amount") or 0),
        "as_of_date": _str(row.get("as_of_date")),
        "analyst": _str(row.get("analyst")),
        "approved_by": _str(row.get("approved_by")),
        "notes": _str(row.get("notes")),
        "created_at": _str(row.get("created_at")),
        "updated_at": _str(row.get("updated_at")),
    }


def _triangle_from_sql(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _str(row.get("id")),
        "line_of_business": _str(row.get("line_of_business")),
        "accident_year": int(row.get("accident_year") or 0),
        "development_month": int(row.get("development_month") or 0),
        "incurred_amount": float(row.get("incurred_amount") or 0),
        "paid_amount": float(row.get("paid_amount") or 0),
        "case_reserve": float(row.get("case_reserve") or 0),
        "claim_count": int(row.get("claim_count") or 0),
        "created_at": _str(row.get("created_at")),
    }


def _rate_from_sql(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _str(row.get("id")),
        "line_of_business": _str(row.get("line_of_business")),
        "segment": _str(row.get("segment")),
        "current_rate": str(float(row.get("current_rate") or 0)),
        "indicated_rate": str(float(row.get("indicated_rate") or 0)),
        "adequacy_ratio": str(float(row.get("adequacy_ratio") or 0)),
        "as_of_date": _str(row.get("as_of_date")),
        "created_at": _str(row.get("created_at")),
    }


# ---------------------------------------------------------------------------
# Actuarial reserve repository
# ---------------------------------------------------------------------------


class SqlActuarialReserveRepository(BaseRepository):
    """Azure SQL implementation of the actuarial reserve repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)
        await self.db.execute_query(
            """INSERT INTO actuarial_reserves
               (id, line_of_business, accident_year, reserve_type,
                carried_amount, indicated_amount, selected_amount,
                as_of_date, analyst, approved_by, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"], entity.get("line_of_business"),
                entity.get("accident_year"), entity.get("reserve_type"),
                entity.get("carried_amount", 0), entity.get("indicated_amount", 0),
                entity.get("selected_amount", 0), entity.get("as_of_date"),
                entity.get("analyst", ""), entity.get("approved_by", ""),
                entity.get("notes", ""), entity["created_at"], entity["updated_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM actuarial_reserves WHERE id = ?", [str(entity_id)]
        )
        return _reserve_from_sql(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM actuarial_reserves"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            if "line_of_business" in filters:
                where.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "accident_year" in filters:
                where.append("accident_year = ?")
                params.append(filters["accident_year"])
            if "reserve_type" in filters:
                where.append("reserve_type = ?")
                params.append(filters["reserve_type"])
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY accident_year DESC, reserve_type OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_reserve_from_sql(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at", "updated_at"):
                continue
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return await self.get_by_id(entity_id)
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE actuarial_reserves SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM actuarial_reserves WHERE id = ?", [str(entity_id)]
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM actuarial_reserves"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            if "line_of_business" in filters:
                where.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "accident_year" in filters:
                where.append("accident_year = ?")
                params.append(filters["accident_year"])
        if where:
            query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


# ---------------------------------------------------------------------------
# Triangle entry repository
# ---------------------------------------------------------------------------


class SqlTriangleRepository(BaseRepository):
    """Azure SQL implementation of the loss triangle entry repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("created_at", now)
        await self.db.execute_query(
            """INSERT INTO loss_triangle_entries
               (id, line_of_business, accident_year, development_month,
                incurred_amount, paid_amount, case_reserve, claim_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"], entity.get("line_of_business"),
                entity.get("accident_year"), entity.get("development_month"),
                entity.get("incurred_amount", 0), entity.get("paid_amount", 0),
                entity.get("case_reserve", 0), entity.get("claim_count", 0),
                entity["created_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM loss_triangle_entries WHERE id = ?", [str(entity_id)]
        )
        return _triangle_from_sql(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM loss_triangle_entries"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            if "line_of_business" in filters:
                where.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "accident_year" in filters:
                where.append("accident_year = ?")
                params.append(filters["accident_year"])
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY accident_year, development_month OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_triangle_from_sql(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at", "updated_at"):
                continue
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return await self.get_by_id(entity_id)
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE loss_triangle_entries SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM loss_triangle_entries WHERE id = ?", [str(entity_id)]
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM loss_triangle_entries"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            if "line_of_business" in filters:
                where.append("line_of_business = ?")
                params.append(filters["line_of_business"])
        if where:
            query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0


# ---------------------------------------------------------------------------
# Rate adequacy repository
# ---------------------------------------------------------------------------


class SqlRateAdequacyRepository(BaseRepository):
    """Azure SQL implementation of the rate adequacy repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("created_at", now)
        await self.db.execute_query(
            """INSERT INTO rate_adequacy
               (id, line_of_business, segment, current_rate, indicated_rate,
                adequacy_ratio, as_of_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                entity["id"], entity.get("line_of_business"),
                entity.get("segment"), entity.get("current_rate"),
                entity.get("indicated_rate"), entity.get("adequacy_ratio"),
                entity.get("as_of_date"), entity["created_at"],
            ],
        )
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT * FROM rate_adequacy WHERE id = ?", [str(entity_id)]
        )
        return _rate_from_sql(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM rate_adequacy"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            if "line_of_business" in filters:
                where.append("line_of_business = ?")
                params.append(filters["line_of_business"])
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY line_of_business, segment OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_rate_from_sql(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key, val in updates.items():
            if key in ("id", "created_at", "updated_at"):
                continue
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return await self.get_by_id(entity_id)
        params.append(str(entity_id))
        await self.db.execute_query(
            f"UPDATE rate_adequacy SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "DELETE FROM rate_adequacy WHERE id = ?", [str(entity_id)]
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM rate_adequacy"
        params: list[Any] = []
        where: list[str] = []
        if filters:
            if "line_of_business" in filters:
                where.append("line_of_business = ?")
                params.append(filters["line_of_business"])
        if where:
            query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
