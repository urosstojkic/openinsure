"""Tests for temporal state (time-travel) and risk-attributes features.

Unit tests for the decompose, format, and endpoint handler logic.
Does NOT require a running database or full app startup.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from openinsure.services.risk_attribute_service import (
    decompose_risk_data,
)

# ---------------------------------------------------------------------------
# Temporal Tables Tests (#178) — SQL generation & repo method
# ---------------------------------------------------------------------------


class TestTemporalQueryMethod:
    """Verify SqlPolicyRepository.get_by_id_as_of generates correct SQL."""

    @pytest.mark.asyncio
    async def test_get_by_id_as_of_calls_temporal_sql(self) -> None:
        """get_by_id_as_of should use FOR SYSTEM_TIME AS OF."""
        from openinsure.infrastructure.repositories.sql_policies import (
            SqlPolicyRepository,
        )

        mock_db = MagicMock()
        mock_row = {
            "id": str(uuid.uuid4()),
            "policy_number": "POL-TEST001",
            "status": "active",
            "product_id": str(uuid.uuid4()),
            "submission_id": str(uuid.uuid4()),
            "insured_id": str(uuid.uuid4()),
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
            "total_premium": 5000.00,
            "written_premium": 5000.00,
            "earned_premium": 0,
            "unearned_premium": 5000.00,
            "bound_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "party_name": "Test Co",
            "product_lob": "cyber",
            "deleted_at": None,
            "row_version": None,
        }
        mock_db.fetch_one = AsyncMock(return_value=mock_row)
        repo = SqlPolicyRepository(mock_db)

        result = await repo.get_by_id_as_of("some-id", "2026-03-01T14:47:00")

        # Verify temporal SQL was used
        call_args = mock_db.fetch_one.call_args
        sql = call_args[0][0]
        assert "FOR SYSTEM_TIME AS OF" in sql
        assert result is not None
        assert result["policy_number"] == "POL-TEST001"

    @pytest.mark.asyncio
    async def test_get_by_id_as_of_falls_back_on_error(self) -> None:
        """If temporal query fails, falls back to current state."""
        from openinsure.infrastructure.repositories.sql_policies import (
            SqlPolicyRepository,
        )

        mock_db = MagicMock()
        mock_row = {
            "id": str(uuid.uuid4()),
            "policy_number": "POL-FALLBACK",
            "status": "active",
            "product_id": str(uuid.uuid4()),
            "submission_id": None,
            "insured_id": str(uuid.uuid4()),
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
            "total_premium": 3000.00,
            "written_premium": 3000.00,
            "earned_premium": 0,
            "unearned_premium": 3000.00,
            "bound_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "party_name": None,
            "product_lob": "cyber",
            "deleted_at": None,
            "row_version": None,
        }
        # First call (temporal) raises, second call (fallback) succeeds
        mock_db.fetch_one = AsyncMock(
            side_effect=[Exception("temporal not enabled"), mock_row]
        )
        repo = SqlPolicyRepository(mock_db)

        result = await repo.get_by_id_as_of("some-id", "2026-03-01")
        assert result is not None
        assert result["policy_number"] == "POL-FALLBACK"
        # Should have been called twice (temporal + fallback)
        assert mock_db.fetch_one.call_count == 2

    @pytest.mark.asyncio
    async def test_get_by_id_as_of_returns_none_when_not_found(self) -> None:
        """Returns None when no row exists at given point in time."""
        from openinsure.infrastructure.repositories.sql_policies import (
            SqlPolicyRepository,
        )

        mock_db = MagicMock()
        mock_db.fetch_one = AsyncMock(return_value=None)
        repo = SqlPolicyRepository(mock_db)

        result = await repo.get_by_id_as_of("nonexistent", "2026-03-01")
        assert result is None


# ---------------------------------------------------------------------------
# Temporal Migration Validation (#178)
# ---------------------------------------------------------------------------


class TestTemporalMigration:
    """Validate migration 018 SQL structure."""

    def test_migration_file_exists(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "018_temporal_tables.sql"
        )
        assert migration.exists()

    def test_migration_has_system_versioning(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "018_temporal_tables.sql"
        )
        sql = migration.read_text(encoding="utf-8")
        assert "SYSTEM_VERSIONING" in sql
        assert "PERIOD FOR SYSTEM_TIME" in sql
        assert "valid_from" in sql
        assert "valid_to" in sql
        assert "policies_history" in sql
        assert "claims_history" in sql

    def test_migration_checks_compatibility(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "018_temporal_tables.sql"
        )
        sql = migration.read_text(encoding="utf-8")
        assert "SERVERPROPERTY" in sql
        assert "EngineEdition" in sql

    def test_migration_is_idempotent(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "018_temporal_tables.sql"
        )
        sql = migration.read_text(encoding="utf-8")
        # Should check if columns/versioning already exist
        assert "IF NOT EXISTS" in sql


# ---------------------------------------------------------------------------
# Risk Attributes Tests (#172) — decompose + endpoint handler logic
# ---------------------------------------------------------------------------


class TestRiskAttributeDecomposition:
    """Test risk attribute decomposition from submission data."""

    def test_full_cyber_risk_decomposition(self) -> None:
        """Decomposes full cyber risk data into correct typed rows."""
        risk_data = {
            "annual_revenue": 5000000,
            "employee_count": 50,
            "industry_sic_code": "7372",
            "security_maturity_score": 3.5,
            "has_mfa": True,
            "has_endpoint_protection": True,
            "has_backup_strategy": True,
            "has_incident_response_plan": False,
            "prior_incidents": 0,
        }
        rows = decompose_risk_data("sub-1", risk_data)
        assert len(rows) == 9

        # Verify types
        by_name = {r["attribute_name"]: r for r in rows}
        assert by_name["annual_revenue"]["attribute_type"] == "numeric"
        assert by_name["annual_revenue"]["numeric_value"] == 5000000.0
        assert by_name["has_mfa"]["attribute_type"] == "boolean"
        assert by_name["has_mfa"]["boolean_value"] is True
        assert by_name["industry_sic_code"]["attribute_type"] == "string"
        assert by_name["industry_sic_code"]["string_value"] == "7372"

    def test_decomposition_preserves_all_groups(self) -> None:
        """Different attribute groups don't collide."""
        rows1 = decompose_risk_data("sub-1", {"annual_revenue": 100}, attribute_group="cyber")
        rows2 = decompose_risk_data("sub-1", {"annual_revenue": 200}, attribute_group="marine")
        assert rows1[0]["attribute_group"] == "cyber"
        assert rows2[0]["attribute_group"] == "marine"


class TestRiskAttributeMigration:
    """Validate migration 019 SQL structure."""

    def test_migration_file_exists(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "019_risk_attributes.sql"
        )
        assert migration.exists()

    def test_migration_has_correct_schema(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "019_risk_attributes.sql"
        )
        sql = migration.read_text(encoding="utf-8")
        assert "risk_attributes" in sql
        assert "submission_id" in sql
        assert "attribute_group" in sql
        assert "attribute_name" in sql
        assert "attribute_type" in sql
        assert "string_value" in sql
        assert "numeric_value" in sql
        assert "boolean_value" in sql
        assert "date_value" in sql
        assert "ON DELETE CASCADE" in sql

    def test_migration_is_idempotent(self) -> None:
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scripts"
            / "migrations"
            / "019_risk_attributes.sql"
        )
        sql = migration.read_text(encoding="utf-8")
        assert "IF OBJECT_ID" in sql or "IF NOT EXISTS" in sql


class TestRiskAttributeEndpointRouter:
    """Verify risk attribute routes are registered correctly."""

    def test_risk_attributes_router_registered(self) -> None:
        """Verify the risk_attributes router is included in the API."""
        from openinsure.api.router import api_v1_router

        paths = [route.path for route in api_v1_router.routes]
        # The risk attributes router has submission-level and analytics-level routes
        assert any("risk-attributes" in p for p in paths)

    def test_submission_risk_attributes_route_exists(self) -> None:
        """GET /submissions/{id}/risk-attributes should be a valid route."""
        from openinsure.api.risk_attributes import router

        paths = [route.path for route in router.routes]
        assert "/submissions/{submission_id}/risk-attributes" in paths

    def test_analytics_risk_attributes_route_exists(self) -> None:
        """GET /analytics/risk-attributes should be a valid route."""
        from openinsure.api.risk_attributes import router

        paths = [route.path for route in router.routes]
        assert "/analytics/risk-attributes" in paths


class TestPersistRiskAttributes:
    """Test persist_risk_attributes with mocked database."""

    @pytest.mark.asyncio
    async def test_persist_deletes_existing_and_inserts(self) -> None:
        """Idempotent upsert: deletes old then inserts new."""
        from openinsure.services.risk_attribute_service import persist_risk_attributes

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=1)

        count = await persist_risk_attributes(
            mock_db,
            "sub-1",
            {"annual_revenue": 5000000, "has_mfa": True},
        )
        assert count == 2
        # First call is DELETE, then 2 INSERTs
        assert mock_db.execute_query.call_count == 3
        # First call should be DELETE
        first_call_sql = mock_db.execute_query.call_args_list[0][0][0]
        assert "DELETE FROM risk_attributes" in first_call_sql

    @pytest.mark.asyncio
    async def test_persist_empty_data_returns_zero(self) -> None:
        """No rows persisted for empty data."""
        from openinsure.services.risk_attribute_service import persist_risk_attributes

        mock_db = MagicMock()
        count = await persist_risk_attributes(mock_db, "sub-1", {})
        assert count == 0
        mock_db.execute_query.assert_not_called()
