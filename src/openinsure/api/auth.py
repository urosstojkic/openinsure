"""API authentication for OpenInsure.

In production, this should be replaced with Microsoft Entra ID JWT validation.
For dev/demo, uses a simple API key mechanism.
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from openinsure.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Verify API key if authentication is required.

    Returns the API key or None if auth is disabled.
    Raises 401 if auth is required but key is missing/invalid.
    """
    if not settings.require_auth:
        return None  # Auth disabled for local dev

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key
