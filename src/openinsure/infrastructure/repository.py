"""Base repository abstraction for OpenInsure.

Defines the contract that both in-memory and SQL implementations follow.
The in-memory variant is used for local development and testing; the SQL
variant targets Azure SQL via pyodbc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID


class BaseRepository(ABC):
    """Abstract base class for entity repositories."""

    @abstractmethod
    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Persist a new entity and return it."""
        ...

    @abstractmethod
    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        """Return the entity with the given ID, or ``None``."""
        ...

    @abstractmethod
    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return a filtered, paginated list of entities."""
        ...

    @abstractmethod
    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Apply *updates* to an entity.  Return the updated entity or ``None``."""
        ...

    @abstractmethod
    async def delete(self, entity_id: UUID | str) -> bool:
        """Delete an entity.  Return ``True`` if it existed."""
        ...

    @abstractmethod
    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Return the number of entities matching *filters*."""
        ...
