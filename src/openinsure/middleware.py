"""HTTP middleware for OpenInsure.

Extracted from ``main.py`` to keep the app entry-point thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import Request

logger = structlog.get_logger(__name__)


async def enforce_broker_scope(request: Request, call_next):  # type: ignore[misc]
    """Block broker users from internal API endpoints (RBAC enforcement).

    Broker-role users may only access ``/api/v1/broker/*`` and
    ``/api/v1/products`` endpoints.  All other ``/api/v1/*`` paths are
    forbidden.  Detection works via the ``X-User-Role`` dev header *and*
    JWT bearer-token claims (production).
    """
    path = request.url.path
    if not path.startswith("/api/v1/"):
        return await call_next(request)

    # Endpoints the broker role is allowed to reach
    broker_allowed = ("/api/v1/broker", "/api/v1/products")
    if any(path.startswith(p) for p in broker_allowed):
        return await call_next(request)

    # Detect broker from dev-mode header (always sent by dashboard)
    is_broker = request.headers.get("x-user-role", "").lower() == "broker"

    # Also detect broker from JWT bearer token claims (production)
    if not is_broker:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            try:
                import base64 as _b64
                import json as _json

                payload_b64 = auth_header[7:].split(".")[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                claims = _json.loads(_b64.urlsafe_b64decode(payload_b64))
                roles = claims.get("roles", [])
                is_broker = "openinsure-broker" in roles
            except Exception:  # noqa: S110
                pass

    if is_broker:
        logger.warning(
            "broker_access_denied",
            path=path,
            msg="Broker attempted to access internal endpoint",
        )
        return JSONResponse(
            status_code=403,
            content={
                "error": "Broker access restricted to /api/v1/broker/* endpoints",
                "code": "BROKER_SCOPE_VIOLATION",
            },
        )

    return await call_next(request)
