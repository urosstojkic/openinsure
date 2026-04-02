"""Health check endpoints for OpenInsure.

Three-tier health probe design for container orchestrators:

* ``/health``  — **Liveness**: is the process alive? Lightweight, no dep checks.
* ``/ready``   — **Readiness**: can the pod serve traffic? Checks all deps.
* ``/startup`` — **Startup**: has the app finished initialising? Heavy checks OK.
"""

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
    """Liveness probe response — lightweight, no dependency checks."""

    status: str
    checks: HealthChecks


class ReadyResponse(BaseModel):
    """Readiness probe response — all dependencies checked."""

    status: str
    checks: dict[str, str]


class StartupResponse(BaseModel):
    """Startup probe response — full dependency verification."""

    status: str
    checks: dict[str, str]
    version: str


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


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Lightweight check that the process is alive. Does **not** call "
    "downstream dependencies — use ``/ready`` for that. Container "
    "orchestrators should restart the pod only when this returns non-200.",
)
async def health() -> HealthResponse:
    """Liveness probe — confirms the process is running.

    This endpoint intentionally skips expensive dependency checks so that
    a slow database or Foundry outage does not trigger a restart loop.
    """
    return HealthResponse(
        status="healthy",
        checks=HealthChecks(api="ok"),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description="Checks all downstream dependencies (SQL, Foundry). Returns "
    "``ready`` only when every configured dependency is reachable. "
    "Container Apps should remove the pod from the load-balancer pool "
    "when this returns non-200.",
)
async def ready() -> ReadyResponse:
    """Readiness probe — checks all downstream dependencies.

    Container Apps configuration:
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
    startupProbe:
      httpGet:
        path: /startup
        port: 8000
      initialDelaySeconds: 3
      periodSeconds: 5
      failureThreshold: 30
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


@router.get(
    "/startup",
    response_model=StartupResponse,
    summary="Startup probe",
    description="Full initialisation check — verifies database and Foundry are "
    "reachable before the orchestrator begins sending liveness/readiness "
    "probes. Allowed to take longer than ``/health``.",
)
async def startup() -> StartupResponse:
    """Startup probe — verifies the app has finished initialising.

    Runs the same dependency checks as ``/ready`` but is only polled during
    container startup (``startupProbe``).  Once this returns 200 the
    orchestrator switches to liveness + readiness probes.
    """
    settings = get_settings()
    checks: dict[str, str] = {"api": "ok"}
    checks["database"] = await _check_database()
    checks["foundry"] = await _check_foundry()

    all_ok = all(v in ("ok", "not_configured") for v in checks.values())
    return StartupResponse(
        status="started" if all_ok else "starting",
        checks=checks,
        version=settings.app_version,
    )
