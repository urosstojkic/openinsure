"""Health check endpoints for OpenInsure."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from openinsure.config import get_settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RootResponse(BaseModel):
    """Root endpoint response."""

    status: str
    service: str
    version: str


class HealthChecks(BaseModel):
    """Individual health-check results."""

    api: str = "ok"


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str
    checks: HealthChecks


class ReadyResponse(BaseModel):
    """Readiness probe response."""

    status: str
    checks: dict[str, str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Service identity endpoint."""
    settings = get_settings()
    return RootResponse(
        status="healthy",
        service="openinsure",
        version=settings.app_version,
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — confirms the process is running."""
    return HealthResponse(status="healthy", checks=HealthChecks())


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Readiness probe — checks downstream dependencies.

    Currently only validates the API layer itself.  Database and broker
    checks will be added once those adapters are wired in.
    """
    checks: dict[str, str] = {"api": "ok"}
    # Future: check database connectivity
    # Future: check message broker connectivity
    all_ok = all(v == "ok" for v in checks.values())
    return ReadyResponse(
        status="ready" if all_ok else "degraded",
        checks=checks,
    )
