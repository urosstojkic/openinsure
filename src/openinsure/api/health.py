"""Health check endpoints for OpenInsure."""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from openinsure.config import get_settings

router = APIRouter()
logger = structlog.get_logger(__name__)


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
    database: str = "unchecked"
    foundry: str = "unchecked"


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str
    checks: HealthChecks


class ReadyResponse(BaseModel):
    """Readiness probe response."""

    status: str
    checks: dict[str, str]


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------


async def _check_database() -> str:
    """Test SQL connectivity by executing a lightweight query."""
    settings = get_settings()
    if settings.storage_mode != "azure" or not settings.sql_connection_string:
        return "not_configured"
    try:
        from openinsure.infrastructure.factory import get_database_adapter

        db = get_database_adapter()
        if db is None:
            return "not_configured"
        conn = db._connect()  # noqa: SLF001
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return "ok"
    except Exception as exc:
        logger.warning("health.database_check_failed", error=str(exc))
        return f"error: {type(exc).__name__}"


async def _check_foundry() -> str:
    """Check if Foundry project endpoint is reachable."""
    settings = get_settings()
    if not settings.foundry_project_endpoint:
        return "not_configured"
    try:
        import urllib.request

        req = urllib.request.Request(  # noqa: S310
            settings.foundry_project_endpoint, method="HEAD"
        )
        req.add_header("User-Agent", "OpenInsure-HealthCheck/1.0")
        urllib.request.urlopen(req, timeout=5)  # noqa: S310
        return "ok"
    except Exception as exc:
        logger.warning("health.foundry_check_failed", error=str(exc))
        return f"error: {type(exc).__name__}"


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
    """Liveness probe — confirms the process is running and core deps reachable.

    Checks SQL connectivity and Foundry availability in addition to API status.
    Returns "healthy" only when all configured dependencies are reachable.
    """
    db_status = await _check_database()
    foundry_status = await _check_foundry()

    checks = HealthChecks(api="ok", database=db_status, foundry=foundry_status)

    # Healthy if API is ok and configured deps aren't in error state
    all_ok = all(v in ("ok", "not_configured", "unchecked") for v in (checks.api, checks.database, checks.foundry))
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        checks=checks,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Readiness probe — checks all downstream dependencies.

    Returns "ready" only when ALL configured dependencies are reachable.
    Container Apps should use this to determine if the pod can serve traffic.

    Probe configuration note for Container Apps (infra-level):
    ```yaml
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 15
      failureThreshold: 3
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 30
    ```
    """
    checks: dict[str, str] = {"api": "ok"}

    checks["database"] = await _check_database()
    checks["foundry"] = await _check_foundry()

    all_ok = all(v in ("ok", "not_configured") for v in checks.values())
    return ReadyResponse(
        status="ready" if all_ok else "degraded",
        checks=checks,
    )
