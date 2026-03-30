"""Tests for input validation and path traversal prevention.

Covers:
- Blob name sanitization in documents API
- Pydantic validation on knowledge endpoints
- Common validation patterns
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from openinsure.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ===========================================================================
# Path traversal tests for document download
# ===========================================================================


class TestDocumentPathSanitization:
    """Test blob_name sanitization prevents path traversal."""

    @pytest.mark.asyncio
    async def test_path_traversal_double_dot(self):
        """Path with .. should be rejected by sanitization."""
        from openinsure.api.documents import _sanitize_blob_name

        with pytest.raises(Exception) as exc_info:
            _sanitize_blob_name("../../etc/passwd")
        assert "traversal" in str(exc_info.value).lower() or exc_info.value.status_code == 400  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_path_traversal_middle_dot_dot(self):
        from openinsure.api.documents import _sanitize_blob_name

        with pytest.raises(Exception):
            _sanitize_blob_name("docs/../../../secrets")

    @pytest.mark.asyncio
    async def test_absolute_path_rejected(self):
        from openinsure.api.documents import _sanitize_blob_name

        with pytest.raises(Exception):
            _sanitize_blob_name("/etc/passwd")

    @pytest.mark.asyncio
    async def test_backslash_rejected(self):
        from openinsure.api.documents import _sanitize_blob_name

        with pytest.raises(Exception):
            _sanitize_blob_name("docs\\secrets\\file.txt")

    @pytest.mark.asyncio
    async def test_empty_blob_name_rejected(self):
        from openinsure.api.documents import _sanitize_blob_name

        with pytest.raises(Exception):
            _sanitize_blob_name("")

    @pytest.mark.asyncio
    async def test_valid_blob_name_passes(self):
        from openinsure.api.documents import _sanitize_blob_name

        result = _sanitize_blob_name("cyber/entity-123/document.pdf")
        assert result == "cyber/entity-123/document.pdf"

    @pytest.mark.asyncio
    async def test_valid_blob_name_endpoint(self):
        """Valid blob names should not be rejected by sanitization."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents/download/cyber/entity-123/document.pdf",
                headers={"X-User-Role": "admin"},
            )
        # Will be 404 since storage isn't configured, but NOT 400
        assert response.status_code == 404


# ===========================================================================
# Knowledge endpoint input validation tests
# ===========================================================================


class TestKnowledgeInputValidation:
    """Test that knowledge PUT endpoints validate input with Pydantic models."""

    @pytest.mark.asyncio
    async def test_update_guidelines_valid(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/knowledge/guidelines/cyber",
                json={"title": "Cyber Guidelines", "content": "Test content"},
                headers={"X-User-Role": "product_manager"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["lob"] == "cyber"

    @pytest.mark.asyncio
    async def test_update_claims_precedent_valid(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/knowledge/claims-precedents/data_breach",
                json={"title": "Breach precedent", "description": "Test precedent"},
                headers={"X-User-Role": "product_manager"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_compliance_rule_valid(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/knowledge/compliance-rules/gdpr",
                json={"title": "GDPR Rule", "description": "Data protection"},
                headers={"X-User-Role": "product_manager"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_guidelines_empty_body(self):
        """Empty body should still be valid (all fields have defaults)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/knowledge/guidelines/cyber",
                json={},
                headers={"X-User-Role": "product_manager"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_guidelines_rejects_non_json(self):
        """Non-JSON body should be rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/knowledge/guidelines/cyber",
                content="not json",
                headers={"Content-Type": "application/json", "X-User-Role": "product_manager"},
            )
        assert response.status_code == 422
