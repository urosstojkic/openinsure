"""Tests for RBAC authentication module."""

import base64
import json

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from openinsure.config import Settings, get_settings
from openinsure.rbac.auth import CurrentUser, get_current_user, require_roles
from openinsure.rbac.roles import Role

# ---------------------------------------------------------------------------
# CurrentUser unit tests
# ---------------------------------------------------------------------------


class TestCurrentUser:
    def test_has_role_true(self):
        user = CurrentUser(user_id="u1", email="a@b.com", display_name="A", roles=[Role.CUO])
        assert user.has_role(Role.CUO) is True

    def test_has_role_false(self):
        user = CurrentUser(user_id="u1", email="a@b.com", display_name="A", roles=[Role.CUO])
        assert user.has_role(Role.CEO) is False

    def test_has_any_role_match(self):
        user = CurrentUser(user_id="u1", email="a@b.com", display_name="A", roles=[Role.BROKER])
        assert user.has_any_role(Role.CEO, Role.BROKER) is True

    def test_has_any_role_no_match(self):
        user = CurrentUser(user_id="u1", email="a@b.com", display_name="A", roles=[Role.BROKER])
        assert user.has_any_role(Role.CEO, Role.CFO) is False

    def test_has_any_role_empty(self):
        user = CurrentUser(user_id="u1", email="a@b.com", display_name="A", roles=[])
        assert user.has_any_role(Role.CEO) is False

    def test_default_deployment_type(self):
        user = CurrentUser(user_id="u1", email="a@b.com", display_name="A", roles=[])
        assert user.deployment_type == "mga"


# ---------------------------------------------------------------------------
# Helper: test app
# ---------------------------------------------------------------------------


def _make_app(*, require_auth: bool = False, api_key: str = "test-key") -> FastAPI:
    """Build a minimal FastAPI app wired with the RBAC auth dependency."""
    app = FastAPI()

    @app.get("/open")
    async def open_endpoint():
        return {"ok": True}

    @app.get("/protected")
    async def protected(user: CurrentUser = Depends(get_current_user)):
        return {"user": user.user_id, "roles": user.roles}

    @app.get("/admin-only")
    async def admin_only(
        user: CurrentUser = Depends(require_roles(Role.PLATFORM_ADMIN)),
    ):
        return {"user": user.user_id}

    settings = Settings(require_auth=require_auth, api_key=api_key, debug=True)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


# ---------------------------------------------------------------------------
# Dev mode
# ---------------------------------------------------------------------------


class TestDevMode:
    def test_no_auth_returns_dev_user(self):
        client = TestClient(_make_app(require_auth=False, api_key=""))
        resp = client.get("/protected")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"] == "dev-user"
        assert Role.CUO in body["roles"]

    def test_api_key_set_enforces_auth_even_without_require_auth(self):
        """When api_key is configured, auth is enforced regardless of require_auth."""
        client = TestClient(_make_app(require_auth=False, api_key=_KEY))
        resp = client.get("/protected")
        assert resp.status_code == 401

    def test_api_key_set_accepts_valid_key_without_require_auth(self):
        """Valid API key works even when require_auth=False."""
        client = TestClient(_make_app(require_auth=False, api_key=_KEY))
        resp = client.get("/protected", headers={"X-API-Key": _KEY})
        assert resp.status_code == 200
        assert resp.json()["user"] == "api-key-user"

    def test_api_key_set_rejects_invalid_key_without_require_auth(self):
        """Invalid API key returns 403 even when require_auth=False."""
        client = TestClient(_make_app(require_auth=False, api_key=_KEY))
        resp = client.get("/protected", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# API key mode
# ---------------------------------------------------------------------------

_KEY = "my-secret-key"


class TestApiKeyMode:
    def test_missing_key_returns_401(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        resp = client.get("/protected")
        assert resp.status_code == 401

    def test_wrong_key_returns_403(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        resp = client.get("/protected", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 403

    def test_valid_key_returns_200(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        resp = client.get("/protected", headers={"X-API-Key": _KEY})
        assert resp.status_code == 200
        assert resp.json()["user"] == "api-key-user"


# ---------------------------------------------------------------------------
# JWT mode
# ---------------------------------------------------------------------------


def _make_jwt(payload: dict) -> str:
    """Build a fake (unsigned) JWT for testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


class TestJWTMode:
    def test_valid_jwt(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        token = _make_jwt({"sub": "jwt-user", "email": "j@b.com", "name": "J", "roles": [Role.CUO]})
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user"] == "jwt-user"

    def test_invalid_jwt_format(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        resp = client.get("/protected", headers={"Authorization": "Bearer not-a-jwt"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# require_roles
# ---------------------------------------------------------------------------


class TestRequireRoles:
    def test_allowed_role(self):
        """Dev user has CUO role; admin-only requires PLATFORM_ADMIN → 403."""
        client = TestClient(_make_app(require_auth=False, api_key=""))
        resp = client.get("/admin-only")
        assert resp.status_code == 403  # dev user is CUO, not PLATFORM_ADMIN

    def test_denied_role_with_jwt(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        token = _make_jwt({"sub": "u", "roles": [Role.BROKER]})
        resp = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_granted_role_with_jwt(self):
        client = TestClient(_make_app(require_auth=True, api_key=_KEY))
        token = _make_jwt({"sub": "u", "roles": [Role.PLATFORM_ADMIN]})
        resp = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
