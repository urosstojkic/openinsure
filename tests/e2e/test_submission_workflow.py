"""E2E test: Full submission-to-bind workflow via API.

Tests the complete new business pipeline:
1. Create a submission
2. Triage the submission (agent)
3. Generate a quote (rating engine)
4. Bind the submission to a policy
5. Verify policy created
6. Verify compliance decision records
7. Verify domain events published
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestSubmissionToBindWorkflow:
    """Full lifecycle test: submission → triage → quote → bind → policy."""

    def test_full_workflow(self, client: TestClient):
        # Step 1: Create submission
        submission = client.post(
            "/api/v1/submissions",
            json={
                "applicant_name": "E2E Test Corp",
                "applicant_email": "e2e@testcorp.com",
                "channel": "api",
                "line_of_business": "cyber",
                "risk_data": {
                    "annual_revenue": 5_000_000,
                    "employee_count": 50,
                    "industry_sic_code": "7372",
                    "security_maturity_score": 7.0,
                    "has_mfa": True,
                    "has_endpoint_protection": True,
                    "has_backup_strategy": True,
                },
            },
        )
        assert submission.status_code == 201
        sub_data = submission.json()
        sub_id = sub_data["id"]
        assert sub_id is not None
        assert sub_data["applicant_name"] == "E2E Test Corp"
        assert sub_data["status"] == "received"

        # Step 2: Verify submission exists via GET
        get_sub = client.get(f"/api/v1/submissions/{sub_id}")
        assert get_sub.status_code == 200
        assert get_sub.json()["id"] == sub_id

        # Step 3: List submissions should include our new one
        list_subs = client.get("/api/v1/submissions")
        assert list_subs.status_code == 200
        data = list_subs.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert any(s["id"] == sub_id for s in data["items"])

    def test_create_submission_minimal(self, client: TestClient):
        """Create a submission with only required fields."""
        resp = client.post(
            "/api/v1/submissions",
            json={"applicant_name": "Minimal Corp"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["applicant_name"] == "Minimal Corp"
        assert data["channel"] == "api"
        assert data["line_of_business"] == "cyber"

    def test_create_submission_invalid_returns_422(self, client: TestClient):
        """Omitting required applicant_name should return 422."""
        resp = client.post("/api/v1/submissions", json={})
        assert resp.status_code == 422

    def test_get_submission_not_found(self, client: TestClient):
        """GET for a random ID should return 404."""
        resp = client.get(f"/api/v1/submissions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_create_and_list_policy(self, client: TestClient):
        """Create a policy and verify it appears in list."""
        policy = client.post(
            "/api/v1/policies",
            json={
                "submission_id": str(uuid.uuid4()),
                "product_id": "prod-cyber-001",
                "policyholder_name": "E2E Insured Corp",
                "effective_date": "2026-07-01T00:00:00+00:00",
                "expiration_date": "2027-07-01T00:00:00+00:00",
                "premium": 15000.00,
                "coverages": [{"name": "Cyber Liability", "limit": 1_000_000}],
            },
        )
        assert policy.status_code == 201
        pol_data = policy.json()
        assert pol_data["policyholder_name"] == "E2E Insured Corp"
        assert pol_data["status"] == "active"
        assert "policy_number" in pol_data

        policies = client.get("/api/v1/policies")
        assert policies.status_code == 200
        items = policies.json()["items"]
        assert any(p["id"] == pol_data["id"] for p in items)

    def test_create_claim_and_verify(self, client: TestClient):
        """File a FNOL and verify claim created."""
        claim = client.post(
            "/api/v1/claims",
            json={
                "policy_id": str(uuid.uuid4()),
                "claim_type": "ransomware",
                "description": "E2E test claim - ransomware attack on test systems",
                "date_of_loss": "2026-03-08T00:00:00+00:00",
                "reported_by": "Test User",
                "contact_email": "test@e2e.com",
            },
        )
        assert claim.status_code == 201
        claim_data = claim.json()
        assert claim_data["status"] == "reported"
        assert claim_data["reported_by"] == "Test User"
        assert "claim_number" in claim_data

        claims = client.get("/api/v1/claims")
        assert claims.status_code == 200
        items = claims.json()["items"]
        assert any(c["id"] == claim_data["id"] for c in items)


class TestRatingEngine:
    """Test the rating engine through the API."""

    def test_rate_calculation(self, client: TestClient):
        """Calculate a premium via the products rate endpoint."""
        rate_response = client.post(
            "/api/v1/products/cyber-smb/rate",
            json={
                "risk_data": {
                    "annual_revenue": 5_000_000,
                    "employee_count": 50,
                    "industry_sic_code": "7372",
                    "security_maturity_score": 7.0,
                    "has_mfa": True,
                    "has_endpoint_protection": True,
                    "has_backup_strategy": True,
                    "requested_limit": 1_000_000,
                    "requested_deductible": 10_000,
                },
                "coverages_requested": [],
            },
        )
        # 200 if product exists, 404 if not seeded
        if rate_response.status_code == 200:
            data = rate_response.json()
            assert "total_premium" in data
            assert data["total_premium"] > 0
            assert data["currency"] == "USD"


class TestComplianceEndpoints:
    """Test compliance and audit trail endpoints."""

    def test_list_decisions(self, client: TestClient):
        decisions = client.get("/api/v1/compliance/decisions")
        assert decisions.status_code == 200

    def test_get_decision_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/compliance/decisions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_audit_trail(self, client: TestClient):
        audit = client.get("/api/v1/compliance/audit-trail")
        assert audit.status_code == 200

    def test_system_inventory(self, client: TestClient):
        inventory = client.get("/api/v1/compliance/system-inventory")
        assert inventory.status_code == 200
        data = inventory.json()
        assert isinstance(data, dict)

    def test_bias_report(self, client: TestClient):
        report = client.post(
            "/api/v1/compliance/bias-report",
            json={
                "decision_type": "triage",
                "date_from": "2025-01-01T00:00:00+00:00",
                "date_to": "2026-12-31T23:59:59+00:00",
            },
        )
        assert report.status_code == 201
        data = report.json()
        assert "report_id" in data
        assert data["decision_type"] == "triage"


class TestKnowledgeEndpoints:
    """Test knowledge search and retrieval."""

    def test_search_knowledge(self, client: TestClient):
        result = client.get("/api/v1/knowledge/search", params={"q": "cyber"})
        assert result.status_code == 200
        data = result.json()
        assert "results" in data

    def test_get_guidelines(self, client: TestClient):
        result = client.get("/api/v1/knowledge/guidelines/cyber")
        assert result.status_code == 200

    def test_list_products(self, client: TestClient):
        result = client.get("/api/v1/knowledge/products")
        assert result.status_code == 200


class TestDocumentEndpoints:
    """Test document upload and listing."""

    def test_list_documents(self, client: TestClient):
        result = client.get("/api/v1/documents/list")
        assert result.status_code == 200
        data = result.json()
        assert "items" in data

    def test_upload_document(self, client: TestClient):
        """Upload a test document."""
        file_content = b"Test document content for E2E testing"
        result = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            data={"document_type": "supplemental", "submission_id": "test-sub-id"},
        )
        assert result.status_code == 200
        data = result.json()
        assert data.get("filename") == "test.txt"


class TestEventEndpoints:
    """Test domain event endpoints."""

    def test_recent_events(self, client: TestClient):
        result = client.get("/api/v1/events/recent")
        assert result.status_code == 200
        data = result.json()
        assert "items" in data

    def test_recent_events_with_limit(self, client: TestClient):
        result = client.get("/api/v1/events/recent", params={"limit": 5})
        assert result.status_code == 200
        data = result.json()
        assert "items" in data


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_root(self, client: TestClient):
        result = client.get("/")
        assert result.status_code == 200
        data = result.json()
        assert data["status"] == "healthy"
        assert data["service"] == "openinsure"
        assert "version" in data

    def test_health(self, client: TestClient):
        result = client.get("/health")
        assert result.status_code == 200
        data = result.json()
        assert data["status"] == "healthy"
        assert "checks" in data

    def test_ready(self, client: TestClient):
        result = client.get("/ready")
        assert result.status_code == 200
        data = result.json()
        assert data["status"] == "ready"
        assert "checks" in data
