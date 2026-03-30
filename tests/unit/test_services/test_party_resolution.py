"""Tests for the party resolution service.

Issue #157 — Customer/Applicant Deduplication.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from openinsure.services.party_resolution import PartyResolutionService, _party_store


@pytest.fixture(autouse=True)
def _clear_party_store():
    """Clear the party store before each test."""
    _party_store.clear()
    yield
    _party_store.clear()


@pytest.fixture
def svc() -> PartyResolutionService:
    return PartyResolutionService()


def _mock_repo() -> AsyncMock:
    """Return an AsyncMock repository with empty list_all."""
    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    return repo


class TestResolveOrCreate:
    """Test party resolution logic."""

    @pytest.mark.asyncio
    async def test_create_new_party(self, svc: PartyResolutionService):
        """First submission for a company should create a new party."""
        party_id = await svc.resolve_or_create({"name": "Acme Corp"})
        assert party_id
        party = await svc.get_party(party_id)
        assert party is not None
        assert party["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_dedup_by_name(self, svc: PartyResolutionService):
        """Same name (case-insensitive) should return the same party."""
        id1 = await svc.resolve_or_create({"name": "Acme Corp"})
        id2 = await svc.resolve_or_create({"name": "acme corp"})
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_dedup_by_tax_id(self, svc: PartyResolutionService):
        """Matching tax_id should return the same party."""
        id1 = await svc.resolve_or_create({"name": "Acme Corp", "tax_id": "12-3456789"})
        id2 = await svc.resolve_or_create({"name": "Acme Corporation", "tax_id": "12-3456789"})
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_dedup_by_registration_number(self, svc: PartyResolutionService):
        """Matching registration_number should return the same party."""
        id1 = await svc.resolve_or_create({"name": "Acme Corp", "registration_number": "REG-001"})
        id2 = await svc.resolve_or_create({"name": "Acme Inc", "registration_number": "REG-001"})
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_different_names_create_different_parties(self, svc: PartyResolutionService):
        """Different names without matching identifiers → different parties."""
        id1 = await svc.resolve_or_create({"name": "Acme Corp"})
        id2 = await svc.resolve_or_create({"name": "Beta Industries"})
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_tax_id_takes_priority_over_name(self, svc: PartyResolutionService):
        """Tax ID match should resolve even if name differs."""
        id1 = await svc.resolve_or_create({"name": "Old Name", "tax_id": "99-1234567"})
        id2 = await svc.resolve_or_create({"name": "New Name", "tax_id": "99-1234567"})
        assert id1 == id2


class TestSearchParties:
    """Test party search."""

    @pytest.mark.asyncio
    async def test_search_by_name(self, svc: PartyResolutionService):
        await svc.resolve_or_create({"name": "Acme Corp"})
        await svc.resolve_or_create({"name": "Beta Industries"})
        results = await svc.search_parties(name="acme")
        assert len(results) == 1
        assert results[0]["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_search_by_tax_id(self, svc: PartyResolutionService):
        await svc.resolve_or_create({"name": "Acme Corp", "tax_id": "12-3456789"})
        results = await svc.search_parties(tax_id="12-3456789")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_no_results(self, svc: PartyResolutionService):
        results = await svc.search_parties(name="Nonexistent")
        assert len(results) == 0


class TestCustomer360:
    """Test customer 360° view."""

    @pytest.mark.asyncio
    async def test_360_party_not_found(self, svc: PartyResolutionService):
        result = await svc.get_customer_360("nonexistent-id")
        assert "error" in result

    @pytest.mark.asyncio
    @patch("openinsure.services.party_resolution.get_submission_repository")
    @patch("openinsure.services.party_resolution.get_policy_repository")
    @patch("openinsure.services.party_resolution.get_claim_repository")
    async def test_360_returns_party(
        self,
        mock_claims: AsyncMock,
        mock_policies: AsyncMock,
        mock_subs: AsyncMock,
        svc: PartyResolutionService,
    ):
        mock_subs.return_value = _mock_repo()
        mock_policies.return_value = _mock_repo()
        mock_claims.return_value = _mock_repo()

        party_id = await svc.resolve_or_create({"name": "Acme Corp"})
        result = await svc.get_customer_360(party_id)
        assert result["party"]["name"] == "Acme Corp"
        assert "summary" in result
