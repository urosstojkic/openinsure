"""Tests for InMemory repository implementations.

Covers CRUD operations, listing, filtering, counting, and edge cases
for the InMemorySubmissionRepository, InMemoryPolicyRepository,
and InMemoryClaimRepository.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_submission(**overrides: Any) -> dict[str, Any]:
    """Build a minimal submission dict with sane defaults."""
    data: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "channel": "email",
        "line_of_business": "cyber",
        "status": "received",
        "applicant_name": "Test Corp",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _make_policy(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "policy_number": f"POL-{uuid.uuid4().hex[:6]}",
        "status": "active",
        "insured_name": "Test Corp",
        "effective_date": "2025-01-01",
        "expiration_date": "2026-01-01",
        "total_premium": 5000.0,
        "created_at": "2025-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _make_claim(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "policy_id": str(uuid.uuid4()),
        "status": "reported",
        "loss_date": "2025-06-01",
        "loss_type": "data_breach",
        "description": "Test claim",
        "created_at": "2025-06-01T00:00:00Z",
    }
    data.update(overrides)
    return data


# ===========================================================================
# Submission Repository Tests
# ===========================================================================


class TestInMemorySubmissionRepository:
    """Test the InMemorySubmissionRepository."""

    @pytest.fixture
    def repo(self):
        from openinsure.infrastructure.repositories.submissions import InMemorySubmissionRepository

        return InMemorySubmissionRepository()

    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, repo):
        sub = _make_submission()
        created = await repo.create(sub)
        assert created["id"] == sub["id"]
        assert created["status"] == "received"

        fetched = await repo.get_by_id(sub["id"])
        assert fetched is not None
        assert fetched["id"] == sub["id"]

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo):
        result = await repo.get_by_id("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self, repo):
        sub = _make_submission()
        await repo.create(sub)

        # Update to triaging (valid transition from received)
        updated = await repo.update(sub["id"], {"status": "triaging"})
        assert updated is not None
        assert updated["status"] == "triaging"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, repo):
        result = await repo.update("nonexistent-id", {"status": "triaging"})
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        sub = _make_submission()
        await repo.create(sub)

        deleted = await repo.delete(sub["id"])
        assert deleted is True

        # Should not exist anymore
        result = await repo.get_by_id(sub["id"])
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, repo):
        result = await repo.delete("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_all_empty(self, repo):
        results = await repo.list_all()
        assert results == []

    @pytest.mark.asyncio
    async def test_list_all_with_items(self, repo):
        for _ in range(5):
            await repo.create(_make_submission())

        results = await repo.list_all()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_list_all_with_filter(self, repo):
        await repo.create(_make_submission(line_of_business="cyber"))
        await repo.create(_make_submission(line_of_business="pi"))
        await repo.create(_make_submission(line_of_business="cyber"))

        results = await repo.list_all(filters={"line_of_business": "cyber"})
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_all_pagination(self, repo):
        for _ in range(10):
            await repo.create(_make_submission())

        page1 = await repo.list_all(skip=0, limit=3)
        assert len(page1) == 3

        page2 = await repo.list_all(skip=3, limit=3)
        assert len(page2) == 3

    @pytest.mark.asyncio
    async def test_count_empty(self, repo):
        assert await repo.count() == 0

    @pytest.mark.asyncio
    async def test_count_with_items(self, repo):
        for _ in range(4):
            await repo.create(_make_submission())
        assert await repo.count() == 4

    @pytest.mark.asyncio
    async def test_count_with_filter(self, repo):
        await repo.create(_make_submission(line_of_business="cyber"))
        await repo.create(_make_submission(line_of_business="pi"))

        assert await repo.count(filters={"line_of_business": "cyber"}) == 1


# ===========================================================================
# Policy Repository Tests
# ===========================================================================


class TestInMemoryPolicyRepository:
    """Test the InMemoryPolicyRepository."""

    @pytest.fixture
    def repo(self):
        from openinsure.infrastructure.repositories.policies import InMemoryPolicyRepository

        return InMemoryPolicyRepository()

    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, repo):
        policy = _make_policy()
        created = await repo.create(policy)
        assert created["id"] == policy["id"]

        fetched = await repo.get_by_id(policy["id"])
        assert fetched is not None
        assert fetched["policy_number"] == policy["policy_number"]

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo):
        assert await repo.get_by_id("nonexistent") is None

    @pytest.mark.asyncio
    async def test_update(self, repo):
        policy = _make_policy()
        await repo.create(policy)

        updated = await repo.update(policy["id"], {"total_premium": 7500.0})
        assert updated is not None
        assert updated["total_premium"] == 7500.0

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        policy = _make_policy()
        await repo.create(policy)

        assert await repo.delete(policy["id"]) is True
        assert await repo.get_by_id(policy["id"]) is None

    @pytest.mark.asyncio
    async def test_list_all(self, repo):
        for _ in range(3):
            await repo.create(_make_policy())

        results = await repo.list_all()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_count(self, repo):
        for _ in range(3):
            await repo.create(_make_policy())

        assert await repo.count() == 3


# ===========================================================================
# Claim Repository Tests
# ===========================================================================


class TestInMemoryClaimRepository:
    """Test the InMemoryClaimRepository."""

    @pytest.fixture
    def repo(self):
        from openinsure.infrastructure.repositories.claims import InMemoryClaimRepository

        return InMemoryClaimRepository()

    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, repo):
        claim = _make_claim()
        created = await repo.create(claim)
        assert created["id"] == claim["id"]

        fetched = await repo.get_by_id(claim["id"])
        assert fetched is not None
        assert fetched["loss_type"] == "data_breach"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo):
        assert await repo.get_by_id("nonexistent") is None

    @pytest.mark.asyncio
    async def test_update(self, repo):
        claim = _make_claim()
        await repo.create(claim)

        updated = await repo.update(claim["id"], {"description": "Updated claim"})
        assert updated is not None
        assert updated["description"] == "Updated claim"

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        claim = _make_claim()
        await repo.create(claim)

        assert await repo.delete(claim["id"]) is True
        assert await repo.get_by_id(claim["id"]) is None

    @pytest.mark.asyncio
    async def test_list_all(self, repo):
        for _ in range(3):
            await repo.create(_make_claim())

        results = await repo.list_all()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_count(self, repo):
        for _ in range(3):
            await repo.create(_make_claim())

        assert await repo.count() == 3

    @pytest.mark.asyncio
    async def test_list_all_with_filter(self, repo):
        pid = str(uuid.uuid4())
        await repo.create(_make_claim(policy_id=pid))
        await repo.create(_make_claim(policy_id=pid))
        await repo.create(_make_claim())

        results = await repo.list_all(filters={"policy_id": pid})
        assert len(results) == 2
