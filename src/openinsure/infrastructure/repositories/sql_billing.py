"""SQL-backed billing repository using Azure SQL Database.

Maps between the API billing account/invoice model and the SQL schema
defined in migration 001 (billing_accounts + invoices tables).
"""

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
    from openinsure.infrastructure.database import DatabaseAdapter, TransactionContext

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


def _json_loads(val: Any) -> Any:
    if val is None:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _billing_plan_from_installments(installments: int) -> str:
    """Map installment count to billing_plan enum for SQL CHECK constraint."""
    plan_map = {1: "full_pay", 4: "quarterly", 12: "monthly"}
    return plan_map.get(installments, "quarterly")


def _installments_from_plan(plan: str) -> int:
    """Map billing_plan back to installment count."""
    plan_map = {"full_pay": 1, "quarterly": 4, "monthly": 12, "agency_bill": 1, "direct_bill": 1}
    return plan_map.get(plan, 4)


class SqlBillingRepository(BaseRepository):
    """Azure SQL implementation of the billing repository.

    The SQL schema stores billing accounts and invoices in separate tables.
    Payments are stored as JSON within the billing_accounts row for simplicity,
    but invoices use their own table for queryability.
    """

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    async def _fetch_invoices(self, account_id: str) -> list[dict[str, Any]]:
        """Fetch invoices for a billing account."""
        rows = await self.db.fetch_all(
            """SELECT id as invoice_id, billing_account_id as account_id,
                      amount, status, issue_date, due_date,
                      paid_amount, line_items, created_at
               FROM invoices
               WHERE billing_account_id = ?
               ORDER BY created_at""",
            [account_id],
        )
        return [
            {
                "invoice_id": _str(r.get("invoice_id")),
                "account_id": _str(r.get("account_id")),
                "amount": float(r.get("amount") or 0),
                "status": _str(r.get("status")) or "draft",
                "due_date": _str(r.get("due_date")),
                "description": "Premium installment",
                "line_items": _json_loads(r.get("line_items")),
                "created_at": _str(r.get("created_at")),
            }
            for r in rows
        ]

    def _from_sql_row(self, row: dict[str, Any], invoices: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Convert SQL row to API billing account dict."""
        total_premium = float(row.get("total_premium") or 0)
        balance_due = float(row.get("balance_due") or 0)
        total_paid = total_premium - balance_due

        rv = row.get("row_version")
        return {
            "id": _str(row.get("id")),
            "policy_id": _str(row.get("policy_id")),
            "policyholder_name": "",  # Not in SQL schema; enriched by caller
            "status": "active" if balance_due > 0 else "paid_in_full",
            "total_premium": total_premium,
            "total_paid": total_paid,
            "balance_due": balance_due,
            "installments": _installments_from_plan(_str(row.get("billing_plan"))),
            "currency": "USD",
            "billing_email": None,
            "payments": [],  # Payments loaded separately if needed
            "invoices": invoices or [],
            "metadata": {},
            "created_at": _str(row.get("created_at")),
            "updated_at": _str(row.get("updated_at")),
            "row_version": rv.hex() if isinstance(rv, (bytes, bytearray)) else None,
        }

    async def create(self, entity: dict[str, Any], *, txn: TransactionContext | None = None) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entity.setdefault("id", str(uuid4()))
        entity.setdefault("created_at", now)
        entity.setdefault("updated_at", now)
        entity.setdefault("payments", [])
        entity.setdefault("invoices", [])

        billing_plan = _billing_plan_from_installments(entity.get("installments", 1))
        sql = """INSERT INTO billing_accounts
               (id, policy_id, billing_plan, total_premium, balance_due,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)"""
        params = [
            entity["id"],
            entity.get("policy_id"),
            billing_plan,
            entity.get("total_premium", 0),
            entity.get("balance_due", entity.get("total_premium", 0)),
            entity["created_at"],
            entity["updated_at"],
        ]
        if txn:
            await txn.async_execute_query(sql, params)
        else:
            await self.db.execute_query(sql, params)
        return entity

    async def get_by_id(self, entity_id: UUID | str, *, include_deleted: bool = False) -> dict[str, Any] | None:
        sql = "SELECT * FROM billing_accounts WHERE id = ?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        row = await self.db.fetch_one(sql, [str(entity_id)])
        if not row:
            return None
        invoices = await self._fetch_invoices(str(entity_id))
        return self._from_sql_row(row, invoices)

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM billing_accounts"
        params: list[Any] = []
        where: list[str] = ["deleted_at IS NULL"]
        if filters:
            if "policy_id" in filters:
                where.append("policy_id = ?")
                params.append(filters["policy_id"])
        query += " WHERE " + " AND ".join(where)
        pag_clause, pag_params = safe_pagination_clause("created_at DESC", skip, limit)
        query += pag_clause
        params.extend(pag_params)
        rows = await self.db.fetch_all(query, params)
        return [self._from_sql_row(r) for r in rows]

    async def update(
        self, entity_id: UUID | str, updates: dict[str, Any], *, expected_version: str | None = None
    ) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        col_map = {"total_premium": "total_premium", "balance_due": "balance_due"}
        for key, val in updates.items():
            if key in ("id", "created_at", "payments", "invoices", "metadata", "row_version"):
                continue
            col = col_map.get(key, key)
            if key == "installments":
                col = "billing_plan"
                val = _billing_plan_from_installments(val)  # noqa: PLW2901
            sets.append(f"{col} = ?")
            params.append(val)
        if not sets:
            return await self.get_by_id(entity_id)
        sets.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(str(entity_id))
        where = "WHERE id = ?"
        if expected_version:
            where += " AND row_version = CONVERT(BINARY(8), ?, 1)"
            params.append(f"0x{expected_version}")
        rowcount = await self.db.execute_query(
            f"UPDATE billing_accounts SET {', '.join(sets)} {where}",  # noqa: S608  # nosec B608
            params,
        )
        if expected_version and rowcount == 0:
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="Record modified by another user")
        return await self.get_by_id(entity_id)

    async def delete(self, entity_id: UUID | str) -> bool:
        try:
            result = await self.db.execute_query(
                "UPDATE billing_accounts SET deleted_at = GETUTCDATE() WHERE id = ? AND deleted_at IS NULL",
                [str(entity_id)],
            )
            return result > 0
        except Exception as exc:
            if "REFERENCE" in str(exc).upper() or "547" in str(exc):
                raise IntegrityConstraintError from exc
            raise

    async def restore(self, entity_id: UUID | str) -> bool:
        result = await self.db.execute_query(
            "UPDATE billing_accounts SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            [str(entity_id)],
        )
        return result > 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = "SELECT COUNT(*) as cnt FROM billing_accounts"
        params: list[Any] = []
        where: list[str] = ["deleted_at IS NULL"]
        if filters:
            if "policy_id" in filters:
                where.append("policy_id = ?")
                params.append(filters["policy_id"])
        query += " WHERE " + " AND ".join(where)
        result = await self.db.fetch_one(query, params)
        return result.get("cnt", 0) if result else 0
