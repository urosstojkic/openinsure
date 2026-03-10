"""Cosmos DB NoSQL adapter for the insurance knowledge graph.

Stores knowledge as JSON documents with entityType as partition key.
Supports: products, guidelines, regulatory rules, coverage definitions.
"""

from __future__ import annotations

from typing import Any

import structlog
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

logger = structlog.get_logger()


class CosmosKnowledgeStore:
    """NoSQL document store for the insurance knowledge graph.

    Each document must have ``id`` and ``entityType`` fields.
    ``entityType`` is used as the partition key.
    """

    def __init__(
        self,
        endpoint: str,
        database_name: str,
        container_name: str = "insurance-graph",
    ) -> None:
        credential = DefaultAzureCredential()
        self._client = CosmosClient(endpoint, credential=credential)
        self._database = self._client.get_database_client(database_name)
        self._container = self._database.get_container_client(container_name)
        logger.info("cosmos.connected", endpoint=endpoint, database=database_name)

    def upsert_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Upsert a knowledge document. Must have 'id' and 'entityType'."""
        return self._container.upsert_item(document)

    def get_document(self, doc_id: str, entity_type: str) -> dict[str, Any] | None:
        """Read a single document by id and partition key."""
        try:
            return self._container.read_item(item=doc_id, partition_key=entity_type)
        except Exception:
            return None

    def query_by_type(self, entity_type: str, **filters: Any) -> list[dict[str, Any]]:
        """Query documents by entityType with optional filters."""
        query = "SELECT * FROM c WHERE c.entityType = @entityType"
        params: list[dict[str, Any]] = [{"name": "@entityType", "value": entity_type}]
        for key, val in filters.items():
            query += f" AND c.{key} = @{key}"
            params.append({"name": f"@{key}", "value": val})
        return list(
            self._container.query_items(
                query=query,
                parameters=params,
                partition_key=entity_type,
            )
        )

    def query_guidelines(self, lob: str) -> list[dict[str, Any]]:
        """Retrieve underwriting guidelines for a line of business."""
        return self.query_by_type("guideline", lob=lob)

    def query_products(self, lob: str | None = None) -> list[dict[str, Any]]:
        """Retrieve product definitions, optionally filtered by LOB."""
        if lob:
            return self.query_by_type("product", line_of_business=lob)
        return self.query_by_type("product")

    def query_regulatory(self, jurisdiction: str) -> list[dict[str, Any]]:
        """Retrieve regulatory requirements for a jurisdiction."""
        return self.query_by_type("regulatory", jurisdiction=jurisdiction)

    def search_knowledge(
        self,
        query_text: str,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Simple text search across knowledge documents."""
        if entity_type:
            sql = "SELECT * FROM c WHERE c.entityType = @type AND CONTAINS(LOWER(c.content), LOWER(@q))"
            params: list[dict[str, Any]] = [
                {"name": "@type", "value": entity_type},
                {"name": "@q", "value": query_text},
            ]
        else:
            sql = "SELECT * FROM c WHERE CONTAINS(LOWER(c.content), LOWER(@q))"
            params = [{"name": "@q", "value": query_text}]
        return list(
            self._container.query_items(
                query=sql,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
