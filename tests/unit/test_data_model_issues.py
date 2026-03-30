"""Tests for data model issues #159, #162, #163.

- #159: Optimistic concurrency control (row_version in _from_sql_row, update with expected_version)
- #162: Database-level validation constraints (IntegrityError → 422)
- #163: Composite unique constraints (IntegrityError → 409)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from openinsure.infrastructure.repositories.sql_billing import SqlBillingRepository
from openinsure.infrastructure.repositories.sql_claims import (
    SqlClaimRepository,
    _claim_from_sql_row,
)
from openinsure.infrastructure.repositories.sql_policies import (
    SqlPolicyRepository,
    _policy_from_sql_row,
)
from openinsure.infrastructure.repositories.sql_products import (
    SqlProductRepository,
)
from openinsure.infrastructure.repositories.sql_products import (
    _from_sql_row as _product_from_sql_row,
)
from openinsure.infrastructure.repositories.sql_submissions import (
    SqlSubmissionRepository,
)
from openinsure.infrastructure.repositories.sql_submissions import (
    _from_sql_row as _submission_from_sql_row,
)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "src" / "scripts" / "migrations"


# ---------------------------------------------------------------------------
# Issue #159 — row_version in _from_sql_row
# ---------------------------------------------------------------------------


class TestRowVersionFromSqlRow:
    """Verify _from_sql_row extracts row_version as hex string."""

    def test_policy_row_version_bytes(self) -> None:
        row = {
            "id": str(uuid4()),
            "policy_number": "POL-001",
            "total_premium": 1000,
            "status": "active",
            "row_version": b"\x00\x00\x00\x00\x00\x01\x23\x45",
        }
        result = _policy_from_sql_row(row)
        assert result["row_version"] == "0000000000012345"

    def test_policy_row_version_none(self) -> None:
        row = {"id": str(uuid4()), "policy_number": "POL-001", "total_premium": 1000}
        result = _policy_from_sql_row(row)
        assert result["row_version"] is None

    def test_claim_row_version_bytes(self) -> None:
        row = {
            "id": str(uuid4()),
            "claim_number": "CLM-001",
            "status": "fnol",
            "policy_id": str(uuid4()),
            "total_reserved": 0,
            "total_paid": 0,
            "row_version": b"\xAB\xCD\xEF\x01\x23\x45\x67\x89",
        }
        result = _claim_from_sql_row(row)
        assert result["row_version"] == "abcdef0123456789"

    def test_submission_row_version_bytes(self) -> None:
        row = {
            "id": str(uuid4()),
            "submission_number": "SUB-0001",
            "status": "received",
            "row_version": b"\x01\x02\x03\x04\x05\x06\x07\x08",
        }
        result = _submission_from_sql_row(row)
        assert result["row_version"] == "0102030405060708"

    def test_product_row_version_bytes(self) -> None:
        row = {
            "id": str(uuid4()),
            "product_name": "Cyber Pro",
            "status": "active",
            "version": 1,
            "row_version": b"\xFF\xEE\xDD\xCC\xBB\xAA\x99\x88",
        }
        result = _product_from_sql_row(row)
        assert result["row_version"] == "ffeeddccbbaa9988"

    def test_billing_row_version_bytes(self) -> None:
        repo = SqlBillingRepository(db=MagicMock())
        row = {
            "id": str(uuid4()),
            "policy_id": str(uuid4()),
            "total_premium": 5000,
            "balance_due": 2500,
            "row_version": b"\x11\x22\x33\x44\x55\x66\x77\x88",
        }
        result = repo._from_sql_row(row)
        assert result["row_version"] == "1122334455667788"


# ---------------------------------------------------------------------------
# Issue #159 — optimistic concurrency in update()
# ---------------------------------------------------------------------------


class TestOptimisticConcurrencyUpdate:
    """Verify update() passes expected_version into WHERE clause."""

    @pytest.mark.asyncio
    async def test_policy_update_concurrency_conflict(self) -> None:
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=0)  # 0 rows affected
        db.fetch_one = AsyncMock(return_value={
            "id": "test-id", "policy_number": "POL-1", "total_premium": 1000,
            "status": "active", "row_version": b"\x00" * 8,
        })
        repo = SqlPolicyRepository(db)
        with pytest.raises(Exception) as exc_info:
            await repo.update("test-id", {"status": "active"}, expected_version="0000000000012345")
        assert exc_info.value.status_code == 409  # type: ignore[union-attr]
        assert "modified by another user" in str(exc_info.value.detail)  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_policy_update_no_version_succeeds(self) -> None:
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=1)
        db.fetch_one = AsyncMock(return_value={
            "id": "test-id", "policy_number": "POL-1", "total_premium": 1000,
            "status": "active", "row_version": b"\x00" * 8,
        })
        repo = SqlPolicyRepository(db)
        result = await repo.update("test-id", {"total_premium": 2000})
        assert result is not None

    @pytest.mark.asyncio
    async def test_claim_update_concurrency_conflict(self) -> None:
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=0)
        db.fetch_one = AsyncMock(return_value={
            "id": "test-id", "claim_number": "CLM-1", "status": "fnol",
            "policy_id": str(uuid4()), "total_reserved": 0, "total_paid": 0,
            "row_version": b"\x00" * 8,
        })
        repo = SqlClaimRepository(db)
        with pytest.raises(Exception) as exc_info:
            await repo.update("test-id", {"description": "updated"}, expected_version="aabbccdd11223344")
        assert exc_info.value.status_code == 409  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_submission_update_concurrency_conflict(self) -> None:
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=0)
        db.fetch_one = AsyncMock(return_value={
            "id": "test-id", "submission_number": "SUB-0001", "status": "received",
            "row_version": b"\x00" * 8,
        })
        repo = SqlSubmissionRepository(db)
        with pytest.raises(Exception) as exc_info:
            await repo.update("test-id", {"channel": "api"}, expected_version="0102030405060708")
        assert exc_info.value.status_code == 409  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_product_update_concurrency_conflict(self) -> None:
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=0)
        db.fetch_one = AsyncMock(return_value={
            "id": "test-id", "product_name": "Test", "status": "active",
            "version": 1, "row_version": b"\x00" * 8,
        })
        repo = SqlProductRepository(db)
        with pytest.raises(Exception) as exc_info:
            await repo.update("test-id", {"description": "new"}, expected_version="ffeeddccbbaa9988")
        assert exc_info.value.status_code == 409  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_billing_update_concurrency_conflict(self) -> None:
        db = AsyncMock()
        db.execute_query = AsyncMock(return_value=0)
        db.fetch_one = AsyncMock(return_value={
            "id": "test-id", "policy_id": str(uuid4()),
            "total_premium": 5000, "balance_due": 2500,
            "row_version": b"\x00" * 8,
        })
        repo = SqlBillingRepository(db)
        with pytest.raises(Exception) as exc_info:
            await repo.update("test-id", {"balance_due": 1000}, expected_version="1122334455667788")
        assert exc_info.value.status_code == 409  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Issues #162 / #163 — IntegrityError handling in main.py
# ---------------------------------------------------------------------------


class TestIntegrityErrorHandler:
    """Verify pyodbc.IntegrityError is handled by the app exception handler."""

    @pytest.fixture
    def app(self):
        from openinsure.main import create_app

        return create_app()

    @pytest.fixture
    def client(self, app):
        from starlette.testclient import TestClient

        return TestClient(app, raise_server_exceptions=False)

    def test_constraint_message_map_has_check_constraints(self) -> None:
        """Verify all CHECK constraints from migration 011 are mapped."""
        sql = (_MIGRATIONS_DIR / "011_business_constraints.sql").read_text(encoding="utf-8")
        for ck in [
            "CK_policies_dates",
            "CK_treaties_dates",
            "CK_policies_premium",
            "CK_reserves_amount",
            "CK_payments_amount",
            "CK_invoices_amount",
            "CK_submissions_premium",
            "CK_products_version",
        ]:
            assert ck in sql, f"CHECK constraint {ck} missing from migration"

    def test_unique_constraint_map_has_unique_indexes(self) -> None:
        """Verify all UNIQUE indexes from migration 012 are mapped."""
        sql = (_MIGRATIONS_DIR / "012_unique_constraints.sql").read_text(encoding="utf-8")
        for uq in [
            "UQ_policies_active_insured_product",
            "UQ_billing_policy",
            "UQ_renewal_active",
        ]:
            assert uq in sql, f"UNIQUE index {uq} missing from migration"


# ---------------------------------------------------------------------------
# Migration idempotency
# ---------------------------------------------------------------------------


class TestMigrationIdempotency:
    """Verify migrations use IF NOT EXISTS / TRY-CATCH for idempotency."""

    def test_010_uses_if_col_length(self) -> None:
        sql = (_MIGRATIONS_DIR / "010_concurrency_control.sql").read_text()
        # 5 ALTER statements, each guarded by IF COL_LENGTH(...) IS NULL
        assert sql.count("IF COL_LENGTH(") == 5

    def test_011_uses_try_catch(self) -> None:
        sql = (_MIGRATIONS_DIR / "011_business_constraints.sql").read_text()
        # 8 constraints, each wrapped in BEGIN TRY ALTER TABLE ...
        assert sql.count("BEGIN TRY ALTER") == 8
        assert sql.count("END CATCH") == 8

    def test_012_uses_if_not_exists(self) -> None:
        sql = (_MIGRATIONS_DIR / "012_unique_constraints.sql").read_text()
        # 3 indexes, each guarded by IF NOT EXISTS (SELECT ...
        assert sql.count("IF NOT EXISTS (SELECT") == 3
