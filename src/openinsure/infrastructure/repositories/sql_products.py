"""SQL-backed product repository using Azure SQL Database."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from openinsure.infrastructure.repository import BaseRepository, safe_pagination_clause

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

# -- JSON field names that are stored as NVARCHAR(MAX) in the products table --
_JSON_FIELDS: set[str] = {
    "coverages",
    "rating_factors",
    "appetite_rules",
    "authority_limits",
    "territories",
    "forms",
    "metadata",
}

# Keys used by the API that map to differently-named SQL columns
_API_TO_SQL_KEY: dict[str, str] = {
    "code": "code",
    "name": "product_name",
    "line_of_business": "line_of_business",
}

# SQL columns that should never appear in UPDATE SET clauses
_SKIP_IN_SQL: set[str] = {
    "id",
    "created_at",
    "updated_at",
    # API-only fields with no direct column
    "product_line",
    "rating_rules",
    "underwriting_rules",
    "rating_factor_tables",
    "version_history",
    "documents",
    "effective_date",
    "expiration_date",
}


def _to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map an API entity dict to SQL column values for INSERT."""

    def _dump(val: Any) -> str | None:
        if val is None:
            return None
        return json.dumps(val) if isinstance(val, (dict, list)) else str(val)

    return {
        "id": entity.get("id"),
        "product_code": entity.get("code", entity.get("product_code")),
        "code": entity.get("code", entity.get("product_code")),
        "product_name": entity.get("name", entity.get("product_name", "")),
        "line_of_business": entity.get("line_of_business", entity.get("product_line", "")),
        "description": entity.get("description", ""),
        "status": entity.get("status", "draft"),
        "version": entity.get("version", 1),
        "coverages": _dump(entity.get("coverages")),
        "rating_factors": _dump(entity.get("rating_factors")),
        "appetite_rules": _dump(entity.get("appetite_rules")),
        "authority_limits": _dump(entity.get("authority_limits")),
        "territories": _dump(entity.get("territories")),
        "forms": _dump(entity.get("forms")),
        "metadata": _dump(entity.get("metadata")),
        "published_at": entity.get("published_at"),
        "effective_date": entity.get("effective_date"),
        "expiration_date": entity.get("expiration_date"),
        "created_by": entity.get("created_by"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API entity keys."""

    def _str(val: Any) -> str:
        if val is None:
            return ""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    def _json_obj(val: Any, default: Any | None = None) -> Any:
        """Deserialise a JSON column — returns dict, list, or *default*."""
        if default is None:
            default = {}
        if val is None:
            return default
        if isinstance(val, (dict, list)):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default

    lob = _str(row.get("line_of_business"))
    created = _str(row.get("created_at"))
    updated = _str(row.get("updated_at"))
    version_raw = row.get("version", 1)
    version_str = str(version_raw) if version_raw is not None else "1"

    return {
        "id": _str(row.get("id")),
        "code": _str(row.get("code") or row.get("product_code")),
        "name": _str(row.get("product_name")),
        "product_line": lob,
        "line_of_business": lob,
        "description": _str(row.get("description")),
        "status": _str(row.get("status")) or "draft",
        "version": version_str,
        "coverages": _json_obj(row.get("coverages"), []),
        "rating_factors": _json_obj(row.get("rating_factors"), []),
        "rating_rules": {},
        "rating_factor_tables": [],
        "underwriting_rules": {},
        "appetite_rules": _json_obj(row.get("appetite_rules"), []),
        "authority_limits": _json_obj(row.get("authority_limits")),
        "territories": _json_obj(row.get("territories"), []),
        "forms": _json_obj(row.get("forms"), []),
        "metadata": _json_obj(row.get("metadata")),
        "version_history": [],
        "effective_date": _str(row.get("effective_date")) or None,
        "expiration_date": _str(row.get("expiration_date")) or None,
        "published_at": _str(row.get("published_at")) or None,
        "created_by": _str(row.get("created_by")) or None,
        "created_at": created,
        "updated_at": updated,
    }


class SqlProductRepository(BaseRepository):
    """Azure SQL implementation of the product repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("status", "draft")
        entity.setdefault("version", 1)
        entity.setdefault("created_at", datetime.now(UTC).isoformat())
        entity.setdefault("updated_at", datetime.now(UTC).isoformat())

        row = _to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO products
               (id, product_code, code, product_name, line_of_business, description,
                status, version, coverages, rating_factors, appetite_rules,
                authority_limits, territories, forms, metadata,
                published_at, effective_date, expiration_date, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["product_code"],
                row["code"],
                row["product_name"],
                row["line_of_business"],
                row["description"],
                row["status"],
                row["version"],
                row["coverages"],
                row["rating_factors"],
                row["appetite_rules"],
                row["authority_limits"],
                row["territories"],
                row["forms"],
                row["metadata"],
                row["published_at"],
                row["effective_date"],
                row["expiration_date"],
                row["created_by"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        return _from_sql_row(row)

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM products WHERE id = ?", [str(entity_id)])
        return _from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM products"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "line_of_business" in filters:
                where_clauses.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "product_line" in filters:
                where_clauses.append("line_of_business = ?")
                params.append(filters["product_line"])
            if "code" in filters:
                where_clauses.append("code = ?")
                params.append(filters["code"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [_from_sql_row(r) for r in rows]

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        seen_cols: set[str] = set()

        for key, val in updates.items():
            if key in _SKIP_IN_SQL:
                continue
            col = _API_TO_SQL_KEY.get(key, key)
            if col in seen_cols:
                continue
            seen_cols.add(col)
            sets.append(f"{col} = ?")
            if isinstance(val, (dict, list)):
                params.append(json.dumps(val))
            else:
                params.append(val)

        if not sets:
            return await self.get_by_id(entity_id)

        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))

        await self.db.execute_query(
            f"UPDATE products SET {', '.join(sets)} WHERE id = ?",  # noqa: S608  # nosec B608 — parameterized
            params,
        )
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query("DELETE FROM products WHERE id = ?", [str(entity_id)])
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM products"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("status = ?")
                params.append(filters["status"])
            if "line_of_business" in filters:
                where_clauses.append("line_of_business = ?")
                params.append(filters["line_of_business"])
            if "product_line" in filters:
                where_clauses.append("line_of_business = ?")
                params.append(filters["product_line"])
            if "code" in filters:
                where_clauses.append("code = ?")
                params.append(filters["code"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
