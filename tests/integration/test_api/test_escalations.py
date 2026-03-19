"""Tests for the escalation service and API."""

import uuid

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app
from openinsure.services import escalation


@pytest.fixture(autouse=True)
def _clear_queue():
    """Reset the in-memory queue between tests."""
    escalation._escalation_queue.clear()
    yield
    escalation._escalation_queue.clear()


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests – escalation service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalate_creates_item():
    item = await escalation.escalate(
        action="bind",
        entity_type="submission",
        entity_id="sub-123",
        requested_by="Maria Lopez",
        requested_role="openinsure-uw-analyst",
        amount=75000.0,
        authority_result={
            "required_role": "openinsure-senior-underwriter",
            "escalation_chain": ["openinsure-senior-underwriter", "openinsure-lob-head"],
            "reason": "Bind exceeds analyst authority.",
        },
    )
    assert item["status"] == "pending"
    assert item["action"] == "bind"
    assert item["amount"] == 75000.0
    assert item["required_role"] == "openinsure-senior-underwriter"
    assert await escalation.count_pending() == 1


@pytest.mark.asyncio
async def test_get_queue_filters_by_status():
    await escalation.escalate(
        action="bind",
        entity_type="submission",
        entity_id="s1",
        requested_by="A",
        requested_role="r",
        amount=100,
        authority_result={},
    )
    await escalation.escalate(
        action="quote",
        entity_type="submission",
        entity_id="s2",
        requested_by="B",
        requested_role="r",
        amount=200,
        authority_result={},
    )

    # Resolve one
    items = await escalation.get_queue()
    await escalation.resolve(items[0]["id"], "approved", "boss", "ok")

    pending = await escalation.get_queue(status="pending")
    assert len(pending) == 1

    approved = await escalation.get_queue(status="approved")
    assert len(approved) == 1


@pytest.mark.asyncio
async def test_get_queue_filters_by_role():
    await escalation.escalate(
        action="bind",
        entity_type="submission",
        entity_id="s1",
        requested_by="A",
        requested_role="r",
        amount=100,
        authority_result={
            "required_role": "openinsure-senior-underwriter",
            "escalation_chain": ["openinsure-senior-underwriter"],
        },
    )
    await escalation.escalate(
        action="reserve",
        entity_type="claim",
        entity_id="c1",
        requested_by="B",
        requested_role="r",
        amount=200,
        authority_result={
            "required_role": "openinsure-claims-manager",
            "escalation_chain": ["openinsure-claims-manager"],
        },
    )

    uw_items = await escalation.get_queue(role="openinsure-senior-underwriter")
    assert len(uw_items) == 1
    assert uw_items[0]["action"] == "bind"


@pytest.mark.asyncio
async def test_resolve_approves():
    item = await escalation.escalate(
        action="settle",
        entity_type="claim",
        entity_id="c-1",
        requested_by="A",
        requested_role="r",
        amount=50000,
        authority_result={},
    )
    resolved = await escalation.resolve(item["id"], "approved", "CUO", "Within limits")
    assert resolved is not None
    assert resolved["status"] == "approved"
    assert resolved["resolved_by"] == "CUO"
    assert await escalation.count_pending() == 0


@pytest.mark.asyncio
async def test_resolve_rejects():
    item = await escalation.escalate(
        action="bind",
        entity_type="submission",
        entity_id="s-1",
        requested_by="A",
        requested_role="r",
        amount=999999,
        authority_result={},
    )
    resolved = await escalation.resolve(item["id"], "rejected", "CEO", "Too risky")
    assert resolved is not None
    assert resolved["status"] == "rejected"


@pytest.mark.asyncio
async def test_resolve_missing_returns_none():
    result = await escalation.resolve("nonexistent", "approved", "X", "Y")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_id():
    item = await escalation.escalate(
        action="quote",
        entity_type="submission",
        entity_id="s-1",
        requested_by="A",
        requested_role="r",
        amount=1000,
        authority_result={},
    )
    found = await escalation.get_by_id(item["id"])
    assert found is not None
    assert found["id"] == item["id"]

    missing = await escalation.get_by_id("nope")
    assert missing is None


# ---------------------------------------------------------------------------
# Integration tests – API endpoints
# ---------------------------------------------------------------------------


def test_escalation_count_starts_at_zero(client: TestClient):
    resp = client.get("/api/v1/escalations/count")
    assert resp.status_code == 200
    assert resp.json()["pending"] == 0


def test_list_escalations_empty(client: TestClient):
    resp = client.get("/api/v1/escalations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_escalation_crud_flow(client: TestClient):
    """Create an escalation via the service, then approve it via the API."""
    import asyncio

    loop = asyncio.new_event_loop()
    item = loop.run_until_complete(
        escalation.escalate(
            action="bind",
            entity_type="submission",
            entity_id="sub-999",
            requested_by="Dev User",
            requested_role="openinsure-uw-analyst",
            amount=75000,
            authority_result={"required_role": "openinsure-senior-underwriter", "escalation_chain": []},
        )
    )
    loop.close()

    # Count should be 1
    resp = client.get("/api/v1/escalations/count")
    assert resp.json()["pending"] == 1

    # List shows the item
    resp = client.get("/api/v1/escalations")
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == item["id"]

    # Get by ID
    resp = client.get(f"/api/v1/escalations/{item['id']}")
    assert resp.status_code == 200
    assert resp.json()["action"] == "bind"

    # Approve
    resp = client.post(
        f"/api/v1/escalations/{item['id']}/approve",
        json={
            "resolved_by": "Sarah Chen",
            "reason": "Premium within acceptable range",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Count back to 0
    resp = client.get("/api/v1/escalations/count")
    assert resp.json()["pending"] == 0


def test_reject_escalation(client: TestClient):
    import asyncio

    loop = asyncio.new_event_loop()
    item = loop.run_until_complete(
        escalation.escalate(
            action="settle",
            entity_type="claim",
            entity_id="clm-001",
            requested_by="Dev User",
            requested_role="openinsure-claims-adjuster",
            amount=500000,
            authority_result={"required_role": "openinsure-cuo"},
        )
    )
    loop.close()

    resp = client.post(
        f"/api/v1/escalations/{item['id']}/reject",
        json={
            "resolved_by": "Alexandra Reed",
            "reason": "Insufficient documentation",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_get_nonexistent_escalation_returns_404(client: TestClient):
    resp = client.get(f"/api/v1/escalations/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_approve_nonexistent_escalation_returns_404(client: TestClient):
    resp = client.post(
        f"/api/v1/escalations/{uuid.uuid4()}/approve",
        json={
            "resolved_by": "X",
            "reason": "Y",
        },
    )
    assert resp.status_code == 404
