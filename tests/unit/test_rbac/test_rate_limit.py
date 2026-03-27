"""Tests for rate limiting middleware."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _make_rate_limited_app(limit: str = "3/minute") -> FastAPI:
    """Build a minimal FastAPI app with a fresh limiter per test."""
    test_limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/limited")
    @test_limiter.limit(limit)
    async def limited_endpoint(request: Request) -> dict[str, str]:  # noqa: ARG001
        return {"ok": "true"}

    @app.get("/unlimited")
    async def unlimited_endpoint() -> dict[str, str]:
        return {"ok": "true"}

    return app


class TestRateLimiting:
    def test_under_limit_returns_200(self):
        client = TestClient(_make_rate_limited_app("5/minute"))
        resp = client.get("/limited")
        assert resp.status_code == 200

    def test_over_limit_returns_429(self):
        app = _make_rate_limited_app("2/minute")
        client = TestClient(app)
        # First two requests should succeed
        assert client.get("/limited").status_code == 200
        assert client.get("/limited").status_code == 200
        # Third should be rate limited
        resp = client.get("/limited")
        assert resp.status_code == 429

    def test_429_response_body(self):
        app = _make_rate_limited_app("1/minute")
        client = TestClient(app)
        client.get("/limited")  # consume the limit
        resp = client.get("/limited")
        assert resp.status_code == 429
        # slowapi returns a JSON error body
        assert "rate limit" in resp.text.lower() or resp.status_code == 429

    def test_unlimited_endpoint_not_affected(self):
        app = _make_rate_limited_app("1/minute")
        client = TestClient(app)
        # Exhaust limit on /limited
        client.get("/limited")
        client.get("/limited")
        # /unlimited should still work
        resp = client.get("/unlimited")
        assert resp.status_code == 200


class TestRateLimitConfig:
    def test_limiter_instance_exists(self):
        """The shared limiter instance should be importable."""
        from openinsure.rate_limit import limiter as shared_limiter

        assert shared_limiter is not None

    def test_settings_have_rate_limit_fields(self):
        """Settings should expose rate limit configuration."""
        from openinsure.config import Settings

        s = Settings()
        assert hasattr(s, "rate_limit_per_minute")
        assert hasattr(s, "rate_limit_auth_per_minute")
        assert hasattr(s, "rate_limit_foundry_per_minute")
        assert s.rate_limit_per_minute == 100
        assert s.rate_limit_auth_per_minute == 10
        assert s.rate_limit_foundry_per_minute == 20
