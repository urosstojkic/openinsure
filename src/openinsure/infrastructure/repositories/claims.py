"""Claim repository implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class InMemoryClaimRepository(BaseRepository):
    """Dict-backed claim store for local development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        self._store[entity["id"]] = entity
        return entity

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        record = self._store.get(str(entity_id))
        if record is None:
            return None
        record.update(updates)
        return record

    async def delete(self, entity_id: UUID | str) -> bool:
        return self._store.pop(str(entity_id), None) is not None

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        return self._store.get(str(entity_id))

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = list(self._store.values())
        for key, val in (filters or {}).items():
            if val is not None:
                results = [r for r in results if r.get(key) == val]
        return results[skip : skip + limit]

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        if not filters:
            return len(self._store)
        items = await self.list_all(filters=filters, skip=0, limit=len(self._store) or 1)
        return len(items)
