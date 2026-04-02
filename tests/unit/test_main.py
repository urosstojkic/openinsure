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


# ---------------------------------------------------------------------------
# Adversarial / edge-case tests
# ---------------------------------------------------------------------------

class TestMainAdversarial:
    """Tests that try to break middleware, handlers, and app creation."""

    def test_broker_malformed_jwt_passes(self):
        """Malformed JWT (not 3 parts) should not crash — just pass through."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/submissions",
            headers={"Authorization": "Bearer not.a.valid.jwt.at.all"},
        )
        # Should not crash, not 403 since role extraction fails gracefully
        assert resp.status_code != 403

    def test_broker_empty_bearer_token(self):
        """Empty bearer token should not crash middleware."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/submissions",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code != 403

    def test_broker_no_roles_in_jwt(self):
        """JWT without 'roles' claim should pass (not broker)."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        payload = {"sub": "user1", "email": "test@test.com"}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        header_b64 = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
        fake_jwt = f"{header_b64}.{payload_b64}.sig"
        resp = client.get(
            "/api/v1/submissions",
            headers={"Authorization": f"Bearer {fake_jwt}"},
        )
        assert resp.status_code != 403

    def test_pyodbc_unique_constraint_returns_409(self):
        """UQ_ constraint → 409 Conflict."""
        app = create_app()

        @app.get("/test-uq-error")
        async def _():
            import pyodbc
            raise pyodbc.IntegrityError("constraint 'UQ_policies_active_insured_product' violated")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-uq-error")
        assert resp.status_code == 409
        assert resp.json()["code"] == "CONFLICT"

    def test_pyodbc_check_constraint_returns_422(self):
        """CK_ constraint → 422 Validation Error."""
        app = create_app()

        @app.get("/test-ck-error")
        async def _():
            import pyodbc
            raise pyodbc.IntegrityError("constraint 'CK_policies_premium' violated")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-ck-error")
        assert resp.status_code == 422
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_pyodbc_unknown_constraint_returns_422(self):
        """Unknown constraint type → 422 generic integrity error."""
        app = create_app()

        @app.get("/test-fk-error")
        async def _():
            import pyodbc
            raise pyodbc.IntegrityError("constraint 'FK_something' violated")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-fk-error")
        assert resp.status_code == 422
        assert resp.json()["code"] == "INTEGRITY_ERROR"

    def test_pyodbc_no_constraint_name_returns_422(self):
        """IntegrityError with no parseable constraint name → 422 fallback."""
        app = create_app()

        @app.get("/test-raw-error")
        async def _():
            import pyodbc
            raise pyodbc.IntegrityError("Something went wrong with the database")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-raw-error")
        assert resp.status_code == 422

    def test_pyodbc_index_violation_pattern(self):
        """Index-style constraint name (unique index) → parsed correctly."""
        app = create_app()

        @app.get("/test-idx-error")
        async def _():
            import pyodbc
            raise pyodbc.IntegrityError("Cannot insert duplicate key, index 'UQ_billing_policy' violated")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-idx-error")
        assert resp.status_code == 409  # UQ_ prefix → 409

    def test_domain_error_with_details(self):
        """DomainError with custom details should include them in response."""
        from openinsure.domain.exceptions import InvalidStateTransitionError

        app = create_app()

        @app.get("/test-state-error")
        async def _():
            raise InvalidStateTransitionError("Submission", "received", "bound", "Must be quoted first")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-state-error")
        assert resp.status_code == 409
        assert resp.json()["code"] == "INVALID_STATE_TRANSITION"

    def test_broker_case_insensitive_role(self):
        """Role header 'Broker' (capitalized) should still trigger scope."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/api/v1/claims", headers={"X-User-Role": "BROKER"})
        # The middleware does .lower() so this should match
        assert resp.status_code == 403

    def test_concurrent_route_registrations(self):
        """Creating multiple apps should not conflict."""
        app1 = create_app()
        app2 = create_app()
        c1 = TestClient(app1, raise_server_exceptions=False)
        c2 = TestClient(app2, raise_server_exceptions=False)
        r1 = c1.get("/health")
        r2 = c2.get("/health")
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_error_handler_returns_request_id(self):
        """Every error response should include a unique request_id."""
        from openinsure.domain.exceptions import PolicyNotFoundError

        app = create_app()

        @app.get("/test-req-id")
        async def _():
            raise PolicyNotFoundError("nonexistent")

        client = TestClient(app, raise_server_exceptions=False)
        r1 = client.get("/test-req-id")
        r2 = client.get("/test-req-id")
        assert "request_id" in r1.json()
        assert "request_id" in r2.json()
        assert r1.json()["request_id"] != r2.json()["request_id"]
