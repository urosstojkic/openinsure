"""Integration tests for API authentication."""

from fastapi.testclient import TestClient

from openinsure.config import Settings, get_settings
from openinsure.main import create_app

_TEST_API_KEY = "test-secret-key-12345"


def _make_settings(*, require_auth: bool, api_key: str = _TEST_API_KEY) -> Settings:
    """Build a Settings object with auth fields overridden."""
    return Settings(
        debug=True,
        require_auth=require_auth,
        api_key=api_key,
    )


def _client_with_auth(require_auth: bool) -> TestClient:
    """Create a TestClient whose app uses the given auth mode."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _make_settings(require_auth=require_auth)
    return TestClient(app)


# ----- Tests -----


def test_health_no_auth_required():
    """Health endpoints work without API key even when auth is required."""
    client = _client_with_auth(require_auth=True)
    for path in ("/", "/health", "/ready"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} should be accessible without auth"


def test_api_no_auth_in_dev_mode():
    """When require_auth=False and no api_key configured, API works without key."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _make_settings(
        require_auth=False, api_key=""
    )
    client = TestClient(app)
    resp = client.get("/api/v1/submissions")
    assert resp.status_code == 200


def test_api_key_enforces_auth_regardless_of_require_auth():
    """When api_key is set, auth is enforced even with require_auth=False (issue #111)."""
    client = _client_with_auth(require_auth=False)
    resp = client.get("/api/v1/submissions")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "API key required"


def test_api_key_enforces_auth_invalid_key():
    """Invalid key returns 403 even when require_auth=False (issue #111)."""
    client = _client_with_auth(require_auth=False)
    resp = client.get("/api/v1/submissions", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Invalid API key"


def test_api_key_enforces_auth_valid_key():
    """Valid key works when require_auth=False but api_key is set (issue #111)."""
    client = _client_with_auth(require_auth=False)
    resp = client.get(
        "/api/v1/submissions",
        headers={"X-API-Key": _TEST_API_KEY},
    )
    assert resp.status_code == 200


def test_api_auth_required():
    """When require_auth=True, missing key returns 401."""
    client = _client_with_auth(require_auth=True)
    resp = client.get("/api/v1/submissions")
    assert resp.status_code == 401


def test_api_auth_invalid_key():
    """When require_auth=True, wrong key returns 403."""
    client = _client_with_auth(require_auth=True)
    resp = client.get("/api/v1/submissions", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 403


def test_api_auth_valid_key():
    """When require_auth=True, correct key returns 200."""
    client = _client_with_auth(require_auth=True)
    resp = client.get(
        "/api/v1/submissions",
        headers={"X-API-Key": _TEST_API_KEY},
    )
    assert resp.status_code == 200
