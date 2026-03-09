"""Integration tests for the Policies API."""

import uuid

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _valid_policy_payload() -> dict:
    return {
        "submission_id": str(uuid.uuid4()),
        "product_id": "prod-cyber-001",
        "policyholder_name": "Acme Cyber Corp",
        "effective_date": "2025-01-01T00:00:00+00:00",
        "expiration_date": "2026-01-01T00:00:00+00:00",
        "premium": 5000.00,
        "coverages": [{"name": "Cyber Liability", "limit": 1_000_000}],
    }


def test_list_policies(client: TestClient):
    """GET /api/v1/policies returns 200."""
    resp = client.get("/api/v1/policies")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_create_policy(client: TestClient):
    """POST with valid data returns 201."""
    resp = client.post("/api/v1/policies", json=_valid_policy_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["policyholder_name"] == "Acme Cyber Corp"
    assert data["status"] == "active"
    assert "id" in data
    assert "policy_number" in data


def test_get_policy_not_found(client: TestClient):
    """GET /api/v1/policies/{random_uuid} returns 404."""
    random_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/policies/{random_id}")
    assert resp.status_code == 404
