"""Authentication and authorization for OpenInsure.

Supports three modes:
1. Dev mode: No auth, default CUO user (for local development)
2. API key mode: X-API-Key header with configurable role (for demo/testing)
3. JWT mode: Bearer token with Entra ID role claims (for production)

JWT validation modes (``jwt_validation_mode`` setting):
- ``"dev"``: Decode payload, check expiry — no signature verification.
- ``"production"``: Full JWKS validation (signature, issuer, audience, expiry).
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request, status

from openinsure.config import Settings, get_settings
from openinsure.rbac.roles import Role

logger = structlog.get_logger(__name__)


@dataclass
class CurrentUser:
    """Represents the authenticated user."""

    user_id: str
    email: str
    display_name: str
    roles: list[str]
    deployment_type: str = "mga"

    def has_role(self, role: str) -> bool:
        """Check whether the user holds a specific role."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """Check whether the user holds at least one of the given roles."""
        return any(r in self.roles for r in roles)


# ---------------------------------------------------------------------------
# Default dev user
# ---------------------------------------------------------------------------
_DEV_USER_ROLES: list[str] = [Role.CUO]


def _dev_user(deployment_type: str) -> CurrentUser:
    """Return a default developer user with CUO role."""
    return CurrentUser(
        user_id="dev-user",
        email="dev@openinsure.local",
        display_name="Dev User",
        roles=list(_DEV_USER_ROLES),
        deployment_type=deployment_type,
    )


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _decode_jwt_payload_unsafe(token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (base64 only).

    Used internally by ``_validate_jwt`` in dev mode.
    """
    parts = token.split(".")
    if len(parts) != 3:
        msg = "Invalid JWT format"
        raise ValueError(msg)
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    decoded = base64.urlsafe_b64decode(payload_b64)
    result: dict[str, Any] = json.loads(decoded)
    return result


def _validate_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Validate a JWT token according to ``jwt_validation_mode``.

    Modes
    -----
    dev
        Decode payload without signature verification.  Check ``exp`` claim
        if present; check ``iss`` if ``jwt_issuer`` is configured.  A warning
        is logged on every call to remind operators that signature verification
        is disabled.

    production
        Full validation via ``PyJWT`` with JWKS (signature, issuer, audience,
        expiry).  Requires ``jwt_issuer`` and ``jwt_audience`` to be set.
    """
    mode = settings.jwt_validation_mode

    if mode == "production":
        return _validate_jwt_production(token, settings)

    # --- dev mode -----------------------------------------------------------
    logger.warning(
        "jwt.dev_mode",
        msg="JWT signature verification is DISABLED in dev mode",
    )
    claims = _decode_jwt_payload_unsafe(token)

    # Even in dev mode, reject expired tokens
    exp = claims.get("exp")
    if exp is not None and float(exp) < time.time():
        msg = "Token has expired"
        raise ValueError(msg)

    # Validate issuer if configured
    if settings.jwt_issuer:
        token_iss = claims.get("iss", "")
        if token_iss != settings.jwt_issuer:
            msg = f"Invalid issuer: {token_iss}"
            raise ValueError(msg)

    return claims


def _validate_jwt_production(token: str, settings: Settings) -> dict[str, Any]:
    """Full JWKS-based JWT validation for Entra ID tokens."""
    import jwt as pyjwt
    from jwt import PyJWKClient

    if not settings.jwt_issuer or not settings.jwt_audience:
        msg = "jwt_issuer and jwt_audience must be configured in production mode"
        raise ValueError(msg)

    # Entra ID v2 JWKS endpoint (derived from issuer)
    issuer = settings.jwt_issuer
    # Standard OIDC: https://login.microsoftonline.com/{tenant}/v2.0
    # JWKS:          https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys
    if "login.microsoftonline.com" in issuer:
        tenant = issuer.rstrip("/").split("/")[-2]
        jwks_url = f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
    else:
        jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"

    jwk_client = PyJWKClient(jwks_url)
    signing_key = jwk_client.get_signing_key_from_jwt(token)

    claims: dict[str, Any] = pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    return claims


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Extract the current user from the request.

    Mode resolution order:
    1. If ``api_key`` is configured (non-empty), enforce auth regardless of
       ``require_auth``.  This closes the auth-bypass where a deployed
       instance with an API key but ``require_auth=False`` allowed
       unauthenticated access.
    2. If no ``api_key`` and ``require_auth=False`` → dev mode (default CUO).
    3. ``X-API-Key`` header → validate against ``settings.api_key``.
    4. ``Authorization: Bearer <jwt>`` → validate token claims.
    5. Fail with 401.
    """
    deployment_type = settings.deployment_type
    auth_enforced = bool(settings.api_key) or settings.require_auth

    # Dev mode — only when no api_key is configured AND require_auth is False
    if not auth_enforced:
        dev_role = request.headers.get("x-user-role")
        if dev_role:
            role_mapping: dict[str, str] = {
                # Frontend UserRole values (AuthContext.tsx)
                "ceo": Role.CEO,
                "cuo": Role.CUO,
                "senior_uw": Role.SENIOR_UNDERWRITER,
                "uw_analyst": Role.UW_ANALYST,
                "claims_manager": Role.CLAIMS_MANAGER,
                "adjuster": Role.CLAIMS_ADJUSTER,
                "cfo": Role.CFO,
                "compliance": Role.COMPLIANCE_OFFICER,
                "product_mgr": Role.PRODUCT_MANAGER,
                "operations": Role.OPERATIONS,
                "broker": Role.BROKER,
                # Common aliases
                "underwriter": Role.UW_ANALYST,
                "claims_adjuster": Role.CLAIMS_ADJUSTER,
                "actuary": Role.ACTUARY,
                "reinsurance": Role.REINSURANCE_MANAGER,
                "finance": Role.FINANCE,
            }
            mapped_role = role_mapping.get(dev_role, dev_role)
            return CurrentUser(
                user_id=f"dev-{dev_role}",
                email=f"{dev_role}@openinsure.local",
                display_name=f"Dev {dev_role.replace('_', ' ').title()}",
                roles=[mapped_role],
                deployment_type=deployment_type,
            )
        return _dev_user(deployment_type)

    # API key mode
    api_key = request.headers.get("x-api-key")
    if api_key:
        if not secrets.compare_digest(api_key, settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )
        return CurrentUser(
            user_id="api-key-user",
            email="api@openinsure.local",
            display_name="API Key User",
            roles=[Role.CUO],
            deployment_type=deployment_type,
        )

    # JWT Bearer mode
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
        try:
            claims = _validate_jwt(token, settings)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid bearer token: {exc}",
            ) from exc
        return CurrentUser(
            user_id=claims.get("sub", "unknown"),
            email=claims.get("email", ""),
            display_name=claims.get("name", "JWT User"),
            roles=claims.get("roles", []),
            deployment_type=deployment_type,
        )

    # No credentials
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key required",
    )


def require_roles(*roles: str) -> Any:
    """Dependency that requires the user to hold at least one of *roles*."""

    async def _check_roles(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.has_any_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(roles)}",
            )
        return user

    return _check_roles
