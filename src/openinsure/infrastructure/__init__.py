"""OpenInsure Infrastructure Adapters — Azure service integrations.

Adapters for Azure SQL, Cosmos DB (Gremlin), Blob Storage,
Event Grid / Service Bus, and Azure AI Search.
"""

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
