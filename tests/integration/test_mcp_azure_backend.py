"""Integration tests: MCP server → Azure backend API.

Verifies that the MCP tool functions (create_submission, triage_submission)
actually call the live Azure backend REST API and return real data.

Run with:
    pytest tests/integration/test_mcp_azure_backend.py -v --azure
"""

from __future__ import annotations

import json

import httpx
import pytest

from openinsure.mcp.server import (
    _BASE_URL,
    _api_url,
    create_submission,
    triage_submission,
)


@pytest.fixture(scope="module")
def backend_reachable() -> bool:
    """Check whether the Azure backend is reachable before running tests."""
    try:
        resp = httpx.get(f"{_BASE_URL}/health", timeout=10)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


def _skip_if_unreachable(reachable: bool) -> None:
    if not reachable:
        pytest.skip(
            f"Azure backend not reachable at {_BASE_URL} — set OPENINSURE_API_BASE_URL or ensure the backend is running"
        )


# ------------------------------------------------------------------
# Sanity: URL builder
# ------------------------------------------------------------------


class TestMCPUrlBuilder:
    """Verify _api_url produces correct paths."""

    def test_submissions_path(self):
        url = _api_url("/submissions")
        assert url == f"{_BASE_URL}/api/v1/submissions"

    def test_triage_path(self):
        url = _api_url("/submissions/abc-123/triage")
        assert url == f"{_BASE_URL}/api/v1/submissions/abc-123/triage"


# ------------------------------------------------------------------
# Live backend tests (require --azure flag)
# ------------------------------------------------------------------


@pytest.mark.azure
@pytest.mark.asyncio
class TestMCPCreateSubmission:
    """MCP create_submission → Azure backend."""

    async def test_creates_submission_via_backend(self, azure_mode, backend_reachable):
        """create_submission should POST to the backend and return a valid submission."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        _skip_if_unreachable(backend_reachable)

        raw = await create_submission(
            applicant="MCP Integration Test Corp",
            line_of_business="cyber",
            annual_revenue=2_500_000,
            employee_count=75,
            industry="Financial Services",
        )

        data = json.loads(raw)

        # Must have a UUID id and expected fields
        assert "id" in data, f"Response missing 'id': {data}"
        assert data.get("applicant_name") == "MCP Integration Test Corp"
        assert data.get("status") == "received"
        assert data.get("line_of_business") == "cyber"

    async def test_submission_retrievable_after_create(self, azure_mode, backend_reachable):
        """A submission created via MCP should be GETable from the backend."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        _skip_if_unreachable(backend_reachable)

        raw = await create_submission(
            applicant="MCP Roundtrip Test",
            annual_revenue=1_000_000,
        )
        sub = json.loads(raw)
        sub_id = sub["id"]

        # Verify via direct HTTP GET (not through MCP) to confirm persistence
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_api_url(f"/submissions/{sub_id}"))
            assert resp.status_code == 200
            fetched = resp.json()
            assert fetched["id"] == sub_id
            assert fetched["applicant_name"] == "MCP Roundtrip Test"


@pytest.mark.azure
@pytest.mark.asyncio
class TestMCPTriageSubmission:
    """MCP triage_submission → Azure backend."""

    async def test_triage_returns_risk_data(self, azure_mode, backend_reachable):
        """triage_submission should POST to /submissions/{id}/triage and return triage results."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        _skip_if_unreachable(backend_reachable)

        # Step 1 — create a submission to triage
        create_raw = await create_submission(
            applicant="MCP Triage Test Corp",
            line_of_business="cyber",
            annual_revenue=10_000_000,
            employee_count=200,
            industry="Healthcare",
        )
        sub = json.loads(create_raw)
        sub_id = sub["id"]

        # Step 2 — triage it
        triage_raw = await triage_submission(sub_id)
        triage = json.loads(triage_raw)

        # Should contain triage results (risk_score, recommendation, etc.)
        assert "error" not in triage, f"Triage returned error: {triage}"
        # The triage response varies by backend version, but it should have
        # meaningful content — at minimum it should not be empty
        assert triage, "Triage returned empty response"

    async def test_triage_nonexistent_returns_error(self, azure_mode, backend_reachable):
        """Triaging a non-existent submission should return an error, not crash."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        _skip_if_unreachable(backend_reachable)

        raw = await triage_submission("00000000-0000-0000-0000-000000000000")
        data = json.loads(raw)
        assert "error" in data


# ------------------------------------------------------------------
# End-to-end: create → triage flow
# ------------------------------------------------------------------


@pytest.mark.azure
@pytest.mark.asyncio
class TestMCPCreateThenTriage:
    """Full create → triage flow through MCP → Azure backend."""

    async def test_full_submission_triage_flow(self, azure_mode, backend_reachable):
        """Create a submission, triage it, and verify the submission status changes."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        _skip_if_unreachable(backend_reachable)

        # Create
        create_raw = await create_submission(
            applicant="MCP E2E Flow Test",
            line_of_business="cyber",
            annual_revenue=5_000_000,
            employee_count=120,
            industry="Technology",
        )
        sub = json.loads(create_raw)
        sub_id = sub["id"]
        assert sub["status"] == "received"

        # Triage
        triage_raw = await triage_submission(sub_id)
        triage = json.loads(triage_raw)
        assert "error" not in triage, f"Triage failed: {triage}"

        # After triage, the submission status should have advanced
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_api_url(f"/submissions/{sub_id}"))
            assert resp.status_code == 200
            updated = resp.json()
            # Status should no longer be "received" after triage
            assert updated["status"] != "received", (
                f"Submission status should advance after triage, got: {updated['status']}"
            )
