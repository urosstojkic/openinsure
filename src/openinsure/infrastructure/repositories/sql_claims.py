"""SQL-backed claims repository using Azure SQL Database."""

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

# -- key mapping between API entity dicts and SQL columns -------------------

_CLAIM_API_TO_SQL_KEY: dict[str, str] = {
    "claim_type": "loss_type",
    "date_of_loss": "loss_date",
}

_CLAIM_SKIP_IN_SQL: set[str] = {
    "reported_by",
    "contact_email",
    "contact_phone",
    "reserves",
    "payments",
    "total_reserved",
    "total_paid",
    "total_incurred",
    "metadata",
    "loss_date",
    "assigned_to",
    "lob",
    "reported_date",
    "policy_number",
}


def _safe_uuid(val: Any) -> str | None:
    """Return *val* as a UUID string, or ``None`` if it is not a valid UUID."""
    if val is None:
        return None
    try:
        return str(UUID(str(val)))
    except (ValueError, AttributeError):
        return None


# The API uses different status values than the SQL CHECK constraint.
# API: reported, under_investigation, reserved, approved, denied, closed, reopened
# SQL: fnol, investigating, reserved, settling, closed, reopened, denied
_STATUS_API_TO_SQL: dict[str, str] = {
    "reported": "fnol",
    "under_investigation": "investigating",
    "approved": "settling",
}
_STATUS_SQL_TO_API: dict[str, str] = {v: k for k, v in _STATUS_API_TO_SQL.items()}


def _api_status_to_sql(status: str) -> str:
    return _STATUS_API_TO_SQL.get(status, status)


def _sql_status_to_api(status: str) -> str:
    return _STATUS_SQL_TO_API.get(status, status)


def _claim_to_sql_row(entity: dict[str, Any]) -> dict[str, Any]:
    """Map API claim dict keys to SQL column names for INSERT."""
    return {
        "id": entity.get("id"),
        "claim_number": entity.get("claim_number"),
        "status": _api_status_to_sql(entity.get("status", "reported")),
        "policy_id": _safe_uuid(entity.get("policy_id")),
        "loss_date": entity.get("date_of_loss"),
        "report_date": entity.get("created_at"),
        "loss_type": entity.get("claim_type"),
        "cause_of_loss": entity.get("cause_of_loss"),
        "description": entity.get("description"),
        "severity": entity.get("severity"),
        "assigned_adjuster": _safe_uuid(entity.get("assigned_adjuster")),
        "fraud_score": entity.get("fraud_score"),
        "closed_at": entity.get("closed_at"),
        "close_reason": entity.get("close_reason"),
        "created_at": entity.get("created_at"),
        "updated_at": entity.get("updated_at"),
    }


def _claim_from_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map SQL column names back to API claim dict keys.

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

    total_reserved = float(row["total_reserved"]) if row.get("total_reserved") else 0.0
    total_paid = float(row["total_paid"]) if row.get("total_paid") else 0.0
    total_incurred = total_reserved + total_paid
    loss_date = _str(row.get("loss_date"))

    return {
        "id": _str(row.get("id")),
        "claim_number": _str(row.get("claim_number")),
        "policy_id": _str(row.get("policy_id")),
        "policy_number": _str(row.get("policy_number")) or "",
        "claim_type": _str(row.get("loss_type")) or "other",
        "status": _sql_status_to_api(_str(row.get("status")) or "fnol"),
        "description": _str(row.get("description")),
        "date_of_loss": loss_date,
        "loss_date": loss_date,
        "severity": _str(row.get("severity")) or "medium",
        "cause_of_loss": _str(row.get("cause_of_loss")),
        "reported_by": "",
        "contact_email": None,
        "contact_phone": None,
        "reserves": [],
        "payments": [],
        "total_reserved": total_reserved,
        "total_paid": total_paid,
        "total_incurred": total_incurred,
        "assigned_to": _str(row.get("assigned_adjuster")) or "",
        "fraud_score": float(row["fraud_score"]) if row.get("fraud_score") else None,
        "lob": "cyber",
        "reported_date": _str(row.get("report_date")) or _str(row.get("created_at")),
        "metadata": {},
        "created_at": _str(row.get("created_at")),
        "updated_at": _str(row.get("updated_at")),
    }


class SqlClaimRepository(BaseRepository):
    """Azure SQL implementation of the claim repository."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("claim_number", f"CLM-{str(uuid4())[:8].upper()}")
        entity.setdefault("status", "fnol")
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)

        row = _claim_to_sql_row(entity)
        await self.db.execute_query(
            """INSERT INTO claims (id, claim_number, status, policy_id,
               loss_date, report_date, loss_type, cause_of_loss,
               description, severity, assigned_adjuster, fraud_score,
               closed_at, close_reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["claim_number"],
                row["status"],
                row["policy_id"],
                row["loss_date"],
                row["report_date"],
                row["loss_type"],
                row["cause_of_loss"],
                row["description"],
                row["severity"],
                row["assigned_adjuster"],
                row["fraud_score"],
                row["closed_at"],
                row["close_reason"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        try:
            from openinsure.services.event_publisher import publish_domain_event

            await publish_domain_event(
                event_type="claim.reported",
                subject=f"/claims/{entity['id']}",
                data={"claim_id": entity["id"], "status": entity.get("status")},
            )
        except Exception:
            logger.warning("Failed to publish claim.reported event for %s", entity["id"])

        # Return a complete dict that matches the API response model
        entity.setdefault("claim_number", row["claim_number"])
        entity.setdefault("claim_type", entity.get("claim_type", "other"))
        entity.setdefault("description", "")
        entity.setdefault("date_of_loss", "")
        entity.setdefault("reported_by", "")
        entity.setdefault("contact_email", None)
        entity.setdefault("contact_phone", None)
        entity.setdefault("reserves", [])
        entity.setdefault("payments", [])
        entity.setdefault("total_reserved", 0.0)
        entity.setdefault("total_paid", 0.0)
        entity.setdefault("metadata", {})
        entity.setdefault("policy_id", "")
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM claims WHERE id = ?", [str(entity_id)])
        return _claim_from_sql_row(row) if row else None

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
                params.append(_api_status_to_sql(filters["status"]))
            if "claim_type" in filters:
                where_clauses.append("loss_type = ?")
                params.append(filters["claim_type"])
            if "policy_id" in filters:
                where_clauses.append("policy_id = ?")
                params.append(filters["policy_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY created_at DESC OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
        rows = await self.db.fetch_all(query, params)
        return [_claim_from_sql_row(r) for r in rows]

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
            if key in ("id", "created_at", "updated_at") or key in _CLAIM_SKIP_IN_SQL:
                continue
            col = _CLAIM_API_TO_SQL_KEY.get(key, key)
            # Map API status values to SQL CHECK-compatible values
            if key == "status":
                val = _api_status_to_sql(val)  # noqa: PLW2901
            sets.append(f"{col} = ?")
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
                params.append(_api_status_to_sql(filters["status"]))
            if "claim_type" in filters:
                where_clauses.append("loss_type = ?")
                params.append(filters["claim_type"])
            if "policy_id" in filters:
                where_clauses.append("policy_id = ?")
                params.append(filters["policy_id"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
