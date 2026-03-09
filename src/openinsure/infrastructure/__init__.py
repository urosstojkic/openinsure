"""OpenInsure Infrastructure Adapters — Azure service integrations.

Adapters for Azure SQL, Cosmos DB (Gremlin), Blob Storage,
Event Grid / Service Bus, and Azure AI Search.

Imports are lazy so the package works even when optional drivers
(e.g. gremlin_python, pyodbc) are not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openinsure.infrastructure.ai_search import SearchAdapter
    from openinsure.infrastructure.blob_storage import BlobStorageAdapter
    from openinsure.infrastructure.cosmos import CosmosGraphAdapter
    from openinsure.infrastructure.database import DatabaseAdapter
    from openinsure.infrastructure.event_bus import EventBusAdapter

__all__ = [
    "BlobStorageAdapter",
    "CosmosGraphAdapter",
    "DatabaseAdapter",
    "EventBusAdapter",
    "SearchAdapter",
]


def __getattr__(name: str):
    """Lazily import adapters on first access."""
    if name == "SearchAdapter":
        from openinsure.infrastructure.ai_search import SearchAdapter

        return SearchAdapter
    if name == "BlobStorageAdapter":
        from openinsure.infrastructure.blob_storage import BlobStorageAdapter

        return BlobStorageAdapter
    if name == "CosmosGraphAdapter":
        from openinsure.infrastructure.cosmos import CosmosGraphAdapter

        return CosmosGraphAdapter
    if name == "DatabaseAdapter":
        from openinsure.infrastructure.database import DatabaseAdapter

        return DatabaseAdapter
    if name == "EventBusAdapter":
        from openinsure.infrastructure.event_bus import EventBusAdapter

        return EventBusAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
