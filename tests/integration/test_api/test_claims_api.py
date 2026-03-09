"""Integration tests for the Claims API."""

import uuid

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _valid_claim_payload() -> dict:
    return {
        "policy_id": str(uuid.uuid4()),
        "claim_type": "data_breach",
        "description": "Unauthorised access to customer PII database.",
        "date_of_loss": "2025-06-01T00:00:00+00:00",
        "reported_by": "Jane Smith",
        "contact_email": "jane@acme.com",
    }


def test_list_claims(client: TestClient):
    """GET /api/v1/claims returns 200."""
    resp = client.get("/api/v1/claims")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_create_claim(client: TestClient):
    """POST with valid FNOL data returns 201."""
    resp = client.post("/api/v1/claims", json=_valid_claim_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "reported"
    assert data["reported_by"] == "Jane Smith"
    assert "id" in data
    assert "claim_number" in data


def test_get_claim_not_found(client: TestClient):
    """GET /api/v1/claims/{random_uuid} returns 404."""
    random_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/claims/{random_id}")
    assert resp.status_code == 404
