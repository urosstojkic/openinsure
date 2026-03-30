"""Tests for health check endpoints with dependency checks."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from openinsure.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "openinsure"


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "api" in data["checks"]
    assert data["checks"]["api"] == "ok"
    # Database and foundry should be present
    assert "database" in data["checks"]
    assert "foundry" in data["checks"]


@pytest.mark.asyncio
async def test_ready_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "degraded")
    assert "api" in data["checks"]
    assert "database" in data["checks"]
    assert "foundry" in data["checks"]


@pytest.mark.asyncio
async def test_ready_api_always_ok():
    """API check should always be OK if the endpoint responds."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.json()["checks"]["api"] == "ok"
