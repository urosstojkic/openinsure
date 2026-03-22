"""Standardized error response model for OpenInsure API."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Additional detail for structured error context."""

    resource_type: str | None = None
    resource_id: str | None = None
    field: str | None = None
    reason: str | None = None


class ErrorResponse(BaseModel):
    """Consistent error response returned by all API endpoints.

    Every error includes a unique ``request_id`` for tracing
    and a machine-readable ``code`` alongside the human-readable message.
    """

    error: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code (e.g. NOT_FOUND)")
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique request ID for tracing")
    detail: ErrorDetail | None = Field(default=None, description="Additional structured context")


def make_error(
    error: str,
    code: str,
    *,
    request_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    field: str | None = None,
    reason: str | None = None,
) -> dict:
    """Build an error response dict suitable for JSONResponse content."""
    detail = None
    if any(v is not None for v in (resource_type, resource_id, field, reason)):
        detail = ErrorDetail(
            resource_type=resource_type,
            resource_id=resource_id,
            field=field,
            reason=reason,
        )
    resp = ErrorResponse(
        error=error,
        code=code,
        request_id=request_id or str(uuid4()),
        detail=detail,
    )
    return resp.model_dump(exclude_none=True)
