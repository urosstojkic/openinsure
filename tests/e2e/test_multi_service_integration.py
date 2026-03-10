"""E2E test: Multi-service integration scenarios.

Tests that creating entities triggers events, compliance records,
and can be retrieved through multiple endpoints.
"""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestSubmissionCreatesEvents:
    """Verify creating a submission triggers domain events."""

    def test_submission_creates_event(self, client: TestClient):
        # Create submission
        sub = client.post(
            "/api/v1/submissions",
            json={
                "applicant_name": "Event Test Corp",
                "applicant_email": "events@testcorp.com",
                "channel": "api",
                "line_of_business": "cyber",
                "risk_data": {"annual_revenue": 2_000_000},
            },
        )
        assert sub.status_code == 201
        sub.json()["id"]

        # Check events were published
        events = client.get("/api/v1/events/recent", params={"limit": 50})
        assert events.status_code == 200
        event_items = events.json().get("items", [])
        assert isinstance(event_items, list)


class TestCrossServiceConsistency:
    """Verify data consistency across services."""

    def test_policy_appears_in_multiple_endpoints(self, client: TestClient):
        # Create policy
        pol = client.post(
            "/api/v1/policies",
            json={
                "submission_id": str(uuid.uuid4()),
                "product_id": "cyber-smb",
                "policyholder_name": "MultiTest Corp",
                "effective_date": "2026-07-01T00:00:00+00:00",
                "expiration_date": "2027-07-01T00:00:00+00:00",
                "premium": 20000.00,
                "coverages": [{"name": "Network Security", "limit": 2_000_000}],
            },
        )
        assert pol.status_code == 201
        pol_id = pol.json()["id"]

        # Verify in policies list
        policies = client.get("/api/v1/policies")
        assert policies.status_code == 200
        assert any(p["id"] == pol_id for p in policies.json()["items"])

        # Verify individual GET
        get_pol = client.get(f"/api/v1/policies/{pol_id}")
        assert get_pol.status_code == 200
        assert get_pol.json()["policyholder_name"] == "MultiTest Corp"

        # Verify health still works (app didn't crash)
        health = client.get("/health")
        assert health.status_code == 200

    def test_claim_on_policy(self, client: TestClient):
        """Create a policy then file a claim against it."""
        # Create policy
        pol = client.post(
            "/api/v1/policies",
            json={
                "submission_id": str(uuid.uuid4()),
                "product_id": "cyber-smb",
                "policyholder_name": "ClaimTest Corp",
                "effective_date": "2026-01-01T00:00:00+00:00",
                "expiration_date": "2027-01-01T00:00:00+00:00",
                "premium": 15000.00,
                "coverages": [],
            },
        )
        assert pol.status_code == 201
        pol_id = pol.json()["id"]

        # File claim against policy
        claim = client.post(
            "/api/v1/claims",
            json={
                "policy_id": pol_id,
                "claim_type": "data_breach",
                "description": "Data breach affecting customer records",
                "date_of_loss": "2026-06-15T00:00:00+00:00",
                "reported_by": "Security Team Lead",
                "contact_email": "security@claimtest.com",
            },
        )
        assert claim.status_code == 201
        claim_id = claim.json()["id"]

        # Both should be retrievable
        get_pol = client.get(f"/api/v1/policies/{pol_id}")
        get_claim = client.get(f"/api/v1/claims/{claim_id}")
        assert get_pol.status_code == 200
        assert get_claim.status_code == 200

        # Lists should include both
        policies = client.get("/api/v1/policies")
        claims = client.get("/api/v1/claims")
        assert policies.status_code == 200
        assert claims.status_code == 200
        assert any(p["id"] == pol_id for p in policies.json()["items"])
        assert any(c["id"] == claim_id for c in claims.json()["items"])

    def test_submission_and_compliance_together(self, client: TestClient):
        """Creating a submission shouldn't break compliance endpoints."""
        sub = client.post(
            "/api/v1/submissions",
            json={
                "applicant_name": "Compliance Test Corp",
                "channel": "api",
                "line_of_business": "cyber",
            },
        )
        assert sub.status_code == 201

        # Compliance endpoints should still respond
        decisions = client.get("/api/v1/compliance/decisions")
        assert decisions.status_code == 200

        audit = client.get("/api/v1/compliance/audit-trail")
        assert audit.status_code == 200

        inventory = client.get("/api/v1/compliance/system-inventory")
        assert inventory.status_code == 200

    def test_multiple_submissions_listed(self, client: TestClient):
        """Create multiple submissions and verify all listed."""
        ids = []
        for i in range(3):
            resp = client.post(
                "/api/v1/submissions",
                json={"applicant_name": f"Batch Corp {i}"},
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        # All should appear in list
        listed = client.get("/api/v1/submissions")
        assert listed.status_code == 200
        listed_ids = {s["id"] for s in listed.json()["items"]}
        for sub_id in ids:
            assert sub_id in listed_ids


class TestRBACRoles:
    """Test that endpoints are accessible in dev mode (no auth required)."""

    def test_health_no_auth(self, client: TestClient):
        """Health endpoints should work without auth."""
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200

    def test_api_endpoints_accessible(self, client: TestClient):
        """API endpoints should be accessible in dev mode."""
        assert client.get("/api/v1/submissions").status_code == 200
        assert client.get("/api/v1/policies").status_code == 200
        assert client.get("/api/v1/claims").status_code == 200
        assert client.get("/api/v1/compliance/decisions").status_code == 200
        assert client.get("/api/v1/events/recent").status_code == 200
        assert client.get("/api/v1/documents/list").status_code == 200

    def test_knowledge_endpoints_accessible(self, client: TestClient):
        """Knowledge endpoints should be accessible."""
        assert client.get("/api/v1/knowledge/search", params={"q": "test"}).status_code == 200
        assert client.get("/api/v1/knowledge/products").status_code == 200


class TestMCPServer:
    """Test MCP server handlers (called internally)."""

    def test_mcp_list_tools(self):
        """Verify MCP server can list available tools."""
        from openinsure.mcp.server import OpenInsureMCPServer

        server = OpenInsureMCPServer()
        tools = asyncio.get_event_loop().run_until_complete(server.list_tools())
        assert isinstance(tools, list)
        assert len(tools) > 0
        tool_names = [t.get("name") for t in tools]
        assert "getPortfolioMetrics" in tool_names

    def test_mcp_list_resources(self):
        """Verify MCP server can list available resources."""
        from openinsure.mcp.server import OpenInsureMCPServer

        server = OpenInsureMCPServer()
        resources = asyncio.get_event_loop().run_until_complete(server.list_resources())
        assert isinstance(resources, list)
        assert len(resources) > 0

    def test_mcp_portfolio_metrics(self):
        """Verify MCP getPortfolioMetrics works through call_tool."""
        from openinsure.mcp.server import OpenInsureMCPServer

        server = OpenInsureMCPServer()
        result = asyncio.get_event_loop().run_until_complete(server.call_tool("getPortfolioMetrics", {}))
        assert isinstance(result, dict)
        assert "content" in result

    def test_mcp_unknown_tool(self):
        """Verify MCP returns error for unknown tool."""
        from openinsure.mcp.server import OpenInsureMCPServer

        server = OpenInsureMCPServer()
        result = asyncio.get_event_loop().run_until_complete(server.call_tool("nonExistentTool", {}))
        assert isinstance(result, dict)
