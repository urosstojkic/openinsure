"""Shared pagination response model for all list endpoints.

Every list endpoint should return a ``PaginatedResponse[T]`` wrapper so
clients always receive a consistent envelope:
``{"items": [...], "total": N, "skip": N, "limit": N}``.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel):
    """Standard paginated list wrapper used across all API list endpoints."""

    items: list  # type: ignore[type-arg]
    total: int
    skip: int
    limit: int
