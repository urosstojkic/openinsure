"""SQL-backed policy repository using Azure SQL Database."""

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

# -- key mapping between API entity dicts and SQL columns -------------------

_POLICY_API_TO_SQL_KEY: dict[str, str] = {
    "policyholder_name": "insured_id",
    "premium": "total_premium",
}

_POLICY_SKIP_IN_SQL: set[str] = {
    "coverages",
    "endorsements",
    "metadata",
    "documents",
    "insured_name",
    "lob",
    "party_name",
}


def _safe_uuid(val: Any) -> str | None:
    """Return *val* as a UUID string, or ``None`` if it is not a valid UUID."""
    if val is None:
        return None
    try:
        return str(UUID(str(val)))
    except (ValueError, AttributeError):
        return None


def _policy_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API policy dict keys to SQL column names for INSERT."""
    return {
        "id": entity.get("id"),
        "policy_number": entity.get("policy_number"),
        "status": entity.get("status", "active"),
        "product_id": entity.get("product_id"),
        "submission_id": _safe_uuid(entity.get("submission_id")),
        "insured_id": entity.get("insured_id") or str(uuid4()),  # auto-generate if no party linked
        "effective_date": entity.get("effective_date"),
        "expiration_date": entity.get("expiration_date"),
        "total_premium": entity.get("premium", entity.get("total_premium")),
        "written_premium": entity.get("written_premium", 0),
        "earned_premium": entity.get("earned_premium", 0),
        "unearned_premium": entity.get("unearned_premium", 0),
        "bound_at": entity.get("bound_at"),
        "cancelled_at": entity.get("cancelled_at"),
        "cancel_reason": entity.get("cancel_reason"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _policy_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API policy dict keys.

    Ensures every value is properly typed — no None where str is expected.
    """

    def _str(val: Any) -> str:
        if val is None:
            return ""
        # Convert SQL datetime objects to ISO 8601 string
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    def _json(val: Any) -> dict[str, Any]:
        if val is None:
            return {}
        if isinstance(val, dict):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}

    premium = float(row["total_premium"]) if row.get("total_premium") else None
    policyholder = _str(row.get("party_name")) or ""
    return {
        "id": _str(row.get("id")),
        "policy_number": _str(row.get("policy_number")),
        "policyholder_name": policyholder,
        "insured_name": policyholder,
        "lob": "cyber",
        "status": _str(row.get("status")) or "active",
        "product_id": _str(row.get("product_id")),
        "submission_id": _str(row.get("submission_id")),
        "effective_date": _str(row.get("effective_date")),
        "expiration_date": _str(row.get("expiration_date")),
        "premium": premium,
        "total_premium": premium,
        "written_premium": float(row["written_premium"]) if row.get("written_premium") else None,
        "earned_premium": float(row["earned_premium"]) if row.get("earned_premium") else None,
        "unearned_premium": float(row["unearned_premium"]) if row.get("unearned_premium") else None,
        "coverages": [],
        "endorsements": [],
        "metadata": {},
        "documents": [],
        "bound_at": _str(row.get("bound_at")) if row.get("bound_at") else None,
        "created_at": _str(row.get("created_at")),
        "updated_at": _str(row.get("updated_at")),
    }


class SqlPolicyRepository(BaseRepository):
    """Azure SQL implementation of the policy repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("policy_number", f"POL-{str(uuid4())[:8].upper()}")
        entity.setdefault("status", "active")
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)

        # Auto-create a party record for the policyholder so the FK is valid.
        insured_id = entity.get("insured_id")
        if not insured_id:
            insured_id = str(uuid4())
            policyholder = entity.get("policyholder_name", "Unknown")
            try:
                await self.db.execute_query(
                    "INSERT INTO parties (id, name, party_type) VALUES (?, ?, ?)",
                    [insured_id, policyholder, "organization"],
                )
                await self.db.execute_query(
                    "INSERT INTO party_roles (party_id, role) VALUES (?, ?)",
                    [insured_id, "insured"],
                )
            except Exception:
                logger.warning("Could not auto-create party for %s", policyholder)
            entity["insured_id"] = insured_id

        # Resolve product_id: if it looks like a code (not a UUID), look it up.
        product_id = entity.get("product_id", "")
        if product_id and not _safe_uuid(product_id):
            try:
                product_row = await self.db.fetch_one(
                    "SELECT id FROM products WHERE product_code = ?",
                    [product_id],
                )
                if product_row:
                    entity["product_id"] = str(product_row["id"])
                else:
                    logger.warning("Product code %s not found, creating placeholder", product_id)
                    new_pid = str(uuid4())
                    await self.db.execute_query(
                        "INSERT INTO products (id, product_code, product_name, line_of_business, status, effective_date) VALUES (?, ?, ?, ?, ?, ?)",
                        [new_pid, product_id, product_id, "cyber", "active", "2025-01-01"],
                    )
                    entity["product_id"] = new_pid
            except Exception:
                logger.warning("Could not resolve product_id %s", product_id)

        row = _policy_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO policies (id, policy_number, status, product_id, submission_id,
               insured_id, effective_date, expiration_date, total_premium,
               written_premium, earned_premium, unearned_premium, bound_at,
               cancelled_at, cancel_reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                row["cancelled_at"],
                row["cancel_reason"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        try:
            from openinsure.services.event_publisher import publish_domain_event

            await publish_domain_event(
                event_type="policy.bound",
                subject=f"/policies/{entity['id']}",
                data={"policy_id": entity["id"], "status": entity.get("status")},
            )
        except Exception:
            logger.warning("Failed to publish policy.bound event for %s", entity["id"])

        # Return a complete dict that matches the API response model
        entity.setdefault("policyholder_name", "")
        entity.setdefault("product_id", "")
        entity.setdefault("submission_id", "")
        entity.setdefault("effective_date", "")
        entity.setdefault("expiration_date", "")
        entity.setdefault("premium", entity.get("premium", entity.get("total_premium")))
        entity.setdefault("total_premium", entity.get("total_premium", entity.get("premium")))
        entity.setdefault("coverages", [])
        entity.setdefault("endorsements", [])
        entity.setdefault("metadata", {})
        entity.setdefault("documents", [])
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one(
            "SELECT p.*, pa.name AS party_name"
            " FROM policies p LEFT JOIN parties pa ON p.insured_id = pa.id"
            " WHERE p.id = ?",
            [str(entity_id)],
        )
        return _policy_from_sql_row(row) if row else None

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT p.*, pa.name AS party_name FROM policies p LEFT JOIN parties pa ON p.insured_id = pa.id"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("p.status = ?")
                params.append(filters["status"])
            if "product_id" in filters:
                where_clauses.append("p.product_id = ?")
                params.append(filters["product_id"])
            if "policyholder_name__contains" in filters:
                where_clauses.append("pa.name LIKE ?")
                params.append(f"%{filters['policyholder_name__contains']}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        pag_clause, pag_params = safe_pagination_clause("p.created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
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
            if key in ("id", "created_at", "updated_at") or key in _POLICY_SKIP_IN_SQL:
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
        query = "SELECT COUNT(*) as cnt FROM policies p"
        join_needed = filters and "policyholder_name__contains" in filters
        if join_needed:
            query += " LEFT JOIN parties pa ON p.insured_id = pa.id"
        params: list[Any] = []
        where_clauses: list[str] = []
        if filters:
            if "status" in filters:
                where_clauses.append("p.status = ?")
                params.append(filters["status"])
            if "product_id" in filters:
                where_clauses.append("p.product_id = ?")
                params.append(filters["product_id"])
            if "policyholder_name__contains" in filters:
                where_clauses.append("pa.name LIKE ?")
                params.append(f"%{filters['policyholder_name__contains']}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
