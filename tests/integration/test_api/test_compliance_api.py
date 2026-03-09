"""Integration tests for the Compliance API."""

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_list_decisions(client: TestClient):
    """GET /api/v1/compliance/decisions returns 200."""
    resp = client.get("/api/v1/compliance/decisions")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert "total" in data


def test_get_audit_trail(client: TestClient):
    """GET /api/v1/compliance/audit-trail returns 200."""
    resp = client.get("/api/v1/compliance/audit-trail")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_system_inventory(client: TestClient):
    """GET /api/v1/compliance/system-inventory returns 200."""
    resp = client.get("/api/v1/compliance/system-inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert "systems" in data
    assert isinstance(data["systems"], list)
    assert data["total"] > 0
