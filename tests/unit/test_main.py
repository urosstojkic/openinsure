"""Unit tests for main.py — app creation, middleware, exception handlers."""

from unittest.mock import MagicMock, patch
import base64
import json

import pytest
from fastapi.testclient import TestClient

from openinsure.main import create_app


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

class TestCreateApp:
    def test_app_creates_successfully(self):
        app = create_app()
        assert app.title == "OpenInsure API"

    def test_app_has_docs_url(self):
        app = create_app()
        assert app.docs_url == "/docs"

    def test_app_includes_openapi_tags(self):
        app = create_app()
        tag_names = [t["name"] for t in app.openapi_tags]
        assert "submissions" in tag_names
        assert "policies" in tag_names
        assert "claims" in tag_names


# ---------------------------------------------------------------------------
# Broker scope enforcement middleware
# ---------------------------------------------------------------------------

class TestBrokerScopeMiddleware:
    def _client(self) -> TestClient:
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_broker_blocked_from_submissions(self):
        client = self._client()
        resp = client.get("/api/v1/submissions", headers={"X-User-Role": "broker"})
        assert resp.status_code == 403
        assert resp.json()["code"] == "BROKER_SCOPE_VIOLATION"

    def test_broker_allowed_broker_endpoints(self):
        client = self._client()
        resp = client.get("/api/v1/broker/submissions", headers={"X-User-Role": "broker"})
        # Should not be 403 — may be 404 or 200 depending on route
        assert resp.status_code != 403

    def test_broker_allowed_products(self):
        client = self._client()
        resp = client.get("/api/v1/products", headers={"X-User-Role": "broker"})
        assert resp.status_code != 403

    def test_non_broker_allowed_submissions(self):
        client = self._client()
        resp = client.get("/api/v1/submissions", headers={"X-User-Role": "cuo"})
        assert resp.status_code != 403

    def test_no_role_header_passes(self):
        client = self._client()
        resp = client.get("/api/v1/submissions")
        assert resp.status_code != 403

    def test_non_api_paths_pass(self):
        """Non-API paths should not trigger broker scope enforcement."""
        client = self._client()
        resp = client.get("/docs", headers={"X-User-Role": "broker"})
        assert resp.status_code != 403

    def test_broker_jwt_detection(self):
        """Broker role in JWT bearer token should be detected."""
        client = self._client()
        # Build a fake JWT with broker role in claims
        payload = {"roles": ["openinsure-broker"], "sub": "user1"}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        header_b64 = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
        fake_jwt = f"{header_b64}.{payload_b64}.signature"
        resp = client.get(
            "/api/v1/submissions",
            headers={"Authorization": f"Bearer {fake_jwt}"},
        )
        assert resp.status_code == 403

    def test_non_broker_jwt_passes(self):
        """Non-broker JWT role should not trigger scope enforcement."""
        client = self._client()
        payload = {"roles": ["openinsure-underwriter"], "sub": "user2"}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        header_b64 = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
        fake_jwt = f"{header_b64}.{payload_b64}.signature"
        resp = client.get(
            "/api/v1/submissions",
            headers={"Authorization": f"Bearer {fake_jwt}"},
        )
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

class TestExceptionHandlers:
    def test_domain_error_handler(self):
        from openinsure.domain.exceptions import SubmissionNotFoundError

        app = create_app()

        @app.get("/test-domain-error")
        async def _():
            raise SubmissionNotFoundError("abc-123")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-domain-error")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "SUBMISSION_NOT_FOUND"
        assert "request_id" in body

    def test_generic_exception_handler_debug(self):
        app = create_app()

        @app.get("/test-crash")
        async def _():
            raise RuntimeError("Something broke")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-crash")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"

    def test_integrity_constraint_error_handler(self):
        from openinsure.infrastructure.repository import IntegrityConstraintError

        app = create_app()

        @app.get("/test-fk-error")
        async def _():
            raise IntegrityConstraintError("Cannot delete: referenced by policies")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-fk-error")
        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------

class TestCORSConfiguration:
    def test_cors_allows_localhost_in_debug(self):
        app = create_app()
        client = TestClient(app)
        resp = client.options(
            "/api/v1/submissions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") in (
            "http://localhost:3000",
            "*",
        )
