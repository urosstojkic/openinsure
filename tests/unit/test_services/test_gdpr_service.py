"""Tests for the GDPR compliance service.

Issue #165 — GDPR Compliance.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from openinsure.services.gdpr_service import GDPRService, _consent_store, _erasure_log
from openinsure.services.party_resolution import PartyResolutionService, _party_store


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear all in-memory stores before each test."""
    _party_store.clear()
    _consent_store.clear()
    _erasure_log.clear()
    yield
    _party_store.clear()
    _consent_store.clear()
    _erasure_log.clear()


@pytest.fixture
def party_svc() -> PartyResolutionService:
    return PartyResolutionService()


@pytest.fixture
def gdpr_svc() -> GDPRService:
    return GDPRService()


def _mock_repo() -> AsyncMock:
    """Return an AsyncMock repository with empty list_all."""
    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    return repo


class TestErasureRequest:
    """Test Art 17: Right to erasure."""

    @pytest.mark.asyncio
    async def test_erasure_party_not_found(self, gdpr_svc: GDPRService):
        result = await gdpr_svc.process_erasure_request("nonexistent-id")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    @patch("openinsure.services.gdpr_service.get_policy_repository")
    async def test_erasure_anonymises_pii(
        self,
        mock_pol_repo: AsyncMock,
        party_svc: PartyResolutionService,
        gdpr_svc: GDPRService,
    ):
        mock_pol_repo.return_value = _mock_repo()

        party_id = await party_svc.resolve_or_create(
            {
                "name": "Acme Corp",
                "tax_id": "12-3456789",
                "contacts": [{"contact_type": "primary", "name": "Jane", "email": "jane@acme.com"}],
            }
        )
        result = await gdpr_svc.process_erasure_request(party_id)
        assert result["status"] == "completed"
        assert "name" in result["fields_anonymised"]

        # Verify PII is redacted
        party = await party_svc.get_party(party_id)
        assert party is not None
        assert party["name"] == "[REDACTED]"
        assert party["tax_id"] is None
        assert party["contacts"] == []

    @pytest.mark.asyncio
    @patch("openinsure.services.gdpr_service.get_policy_repository")
    async def test_erasure_blocked_by_active_policy(
        self,
        mock_pol_repo: AsyncMock,
        party_svc: PartyResolutionService,
        gdpr_svc: GDPRService,
    ):
        repo = AsyncMock()
        repo.list_all = AsyncMock(
            return_value=[
                {"insured_id": "will-be-set", "status": "active", "id": "pol-1"},
            ]
        )
        mock_pol_repo.return_value = repo

        party_id = await party_svc.resolve_or_create({"name": "Acme Corp"})
        # Patch the active policy to reference our party
        repo.list_all.return_value[0]["insured_id"] = party_id

        result = await gdpr_svc.process_erasure_request(party_id)
        assert result["status"] == "blocked"
        assert result["active_policy_count"] == 1


class TestDataExport:
    """Test Art 20: Data portability."""

    @pytest.mark.asyncio
    async def test_export_party_not_found(self, gdpr_svc: GDPRService):
        result = await gdpr_svc.export_personal_data("nonexistent-id")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    @patch("openinsure.services.party_resolution.get_submission_repository")
    @patch("openinsure.services.party_resolution.get_policy_repository")
    @patch("openinsure.services.party_resolution.get_claim_repository")
    async def test_export_returns_personal_data(
        self,
        mock_claims: AsyncMock,
        mock_policies: AsyncMock,
        mock_subs: AsyncMock,
        party_svc: PartyResolutionService,
        gdpr_svc: GDPRService,
    ):
        mock_subs.return_value = _mock_repo()
        mock_policies.return_value = _mock_repo()
        mock_claims.return_value = _mock_repo()

        party_id = await party_svc.resolve_or_create({"name": "Acme Corp"})
        result = await gdpr_svc.export_personal_data(party_id)
        assert result["status"] == "completed"
        assert result["personal_data"]["name"] == "Acme Corp"


class TestConsentTracking:
    """Test Art 7: Consent tracking."""

    @pytest.mark.asyncio
    async def test_grant_consent(self, gdpr_svc: GDPRService):
        record = await gdpr_svc.grant_consent(
            party_id="party-1",
            purpose="insurance_underwriting",
            evidence="Online form submission",
        )
        assert record["status"] == "granted"
        assert record["purpose"] == "insurance_underwriting"

    @pytest.mark.asyncio
    async def test_get_consent_status(self, gdpr_svc: GDPRService):
        await gdpr_svc.grant_consent("party-1", "marketing")
        await gdpr_svc.grant_consent("party-1", "profiling")
        records = await gdpr_svc.get_consent_status("party-1")
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_withdraw_consent(self, gdpr_svc: GDPRService):
        await gdpr_svc.grant_consent("party-1", "marketing")
        result = await gdpr_svc.withdraw_consent("party-1", "marketing")
        assert result["status"] == "withdrawn"
        assert result["withdrawn_count"] == 1

        # Verify consent is withdrawn
        records = await gdpr_svc.get_consent_status("party-1")
        assert all(r["status"] == "withdrawn" for r in records)

    @pytest.mark.asyncio
    async def test_grant_replaces_existing(self, gdpr_svc: GDPRService):
        """Granting consent again withdraws the old one."""
        await gdpr_svc.grant_consent("party-1", "marketing")
        await gdpr_svc.grant_consent("party-1", "marketing")
        records = await gdpr_svc.get_consent_status("party-1")
        granted = [r for r in records if r["status"] == "granted"]
        assert len(granted) == 1


class TestRetentionPolicies:
    """Test data retention policies."""

    @pytest.mark.asyncio
    async def test_list_retention_policies(self, gdpr_svc: GDPRService):
        policies = await gdpr_svc.list_retention_policies()
        assert len(policies) == 4
        entity_types = {p["entity_type"] for p in policies}
        assert entity_types == {"policies", "claims", "submissions", "parties"}
