"""Integration tests for the Submissions API."""

import uuid

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client: TestClient):
    """GET / returns 200 with healthy status."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "openinsure"
    assert "version" in data


def test_health_check(client: TestClient):
    """GET /health returns 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_list_submissions(client: TestClient):
    """GET /api/v1/submissions returns 200 with items list."""
    resp = client.get("/api/v1/submissions")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert "total" in data
    assert "skip" in data
    assert "limit" in data


def test_create_submission(client: TestClient):
    """POST /api/v1/submissions with valid data returns 201."""
    payload = {
        "applicant_name": "Acme Cyber Corp",
        "applicant_email": "contact@acme.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 5_000_000},
    }
    resp = client.post("/api/v1/submissions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["applicant_name"] == "Acme Cyber Corp"
    assert data["status"] == "received"
    assert "id" in data


def test_create_submission_invalid_data(client: TestClient):
    """POST with missing required fields returns 422."""
    resp = client.post("/api/v1/submissions", json={})
    assert resp.status_code == 422


def test_get_submission_not_found(client: TestClient):
    """GET /api/v1/submissions/{random_uuid} returns 404."""
    random_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/submissions/{random_id}")
    assert resp.status_code == 404


def test_list_submissions_with_status_filter(client: TestClient):
    """Filter by status works."""
    # Create a submission first
    client.post(
        "/api/v1/submissions",
        json={"applicant_name": "Filter Test Corp"},
    )
    resp = client.get("/api/v1/submissions", params={"status": "received"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["status"] == "received"


def test_list_submissions_pagination(client: TestClient):
    """skip/limit pagination works."""
    # Create a couple of submissions
    for i in range(3):
        client.post(
            "/api/v1/submissions",
            json={"applicant_name": f"Paging Corp {i}"},
        )

    resp = client.get("/api/v1/submissions", params={"skip": 0, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 2
    assert len(data["items"]) <= 2
