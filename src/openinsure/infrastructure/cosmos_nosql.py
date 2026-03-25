# mypy: ignore-errors
"""Cosmos DB NoSQL adapter for the insurance knowledge graph.

Stores knowledge as JSON documents with entityType as partition key.
Supports: products, guidelines, regulatory rules, coverage definitions,
claims precedents, compliance rules, industry profiles, jurisdiction rules,
billing rules, workflow rules, and rating factors.

Authentication: tries ``DefaultAzureCredential`` (RBAC) first, falls back
to key-based auth when ``cosmos_key`` is provided.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

logger = structlog.get_logger()


def _cosmos_credential(cosmos_key: str = ""):
    """Return RBAC credential or key-based credential."""
    if cosmos_key:
        return cosmos_key
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


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
        *,
        cosmos_key: str = "",
    ) -> None:
        credential = _cosmos_credential(cosmos_key)
        self._client = CosmosClient(endpoint, credential=credential)
        self._database = self._client.get_database_client(database_name)
        self._container = self._database.get_container_client(container_name)
        logger.info(
            "cosmos.connected",
            endpoint=endpoint,
            database=database_name,
            auth="key" if cosmos_key else "rbac",
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def upsert_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Upsert a knowledge document. Must have 'id' and 'entityType'."""
        document.setdefault("updated_at", datetime.now(UTC).isoformat())
        return self._container.upsert_item(document)

    def bulk_upsert(self, documents: list[dict[str, Any]]) -> int:
        """Upsert many documents. Returns count of successfully written docs."""
        now = datetime.now(UTC).isoformat()
        count = 0
        for doc in documents:
            doc.setdefault("updated_at", now)
            self._container.upsert_item(doc)
            count += 1
        return count

    def get_document(self, doc_id: str, entity_type: str) -> dict[str, Any] | None:
        """Read a single document by id and partition key."""
        try:
            return self._container.read_item(item=doc_id, partition_key=entity_type)
        except CosmosResourceNotFoundError:
            return None
        except Exception:
            return None

    def delete_document(self, doc_id: str, entity_type: str) -> bool:
        """Delete a document by id and partition key."""
        try:
            self._container.delete_item(item=doc_id, partition_key=entity_type)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

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

    def query_rating_factors(self, lob: str) -> list[dict[str, Any]]:
        """Retrieve rating factor tables for a line of business."""
        return self.query_by_type("rating_factor", lob=lob)

    def query_coverage_options(self, lob: str) -> list[dict[str, Any]]:
        """Retrieve coverage options for a line of business."""
        return self.query_by_type("coverage_option", lob=lob)

    def query_claims_precedents(self, claim_type: str | None = None) -> list[dict[str, Any]]:
        """Retrieve claims precedents, optionally filtered by claim_type."""
        if claim_type:
            return self.query_by_type("claims_precedent", claim_type=claim_type)
        return self.query_by_type("claims_precedent")

    def query_compliance_rules(self, framework: str | None = None) -> list[dict[str, Any]]:
        """Retrieve compliance rules, optionally filtered by framework."""
        if framework:
            return self.query_by_type("compliance_rule", framework=framework)
        return self.query_by_type("compliance_rule")

    def query_industry_profiles(self, industry: str | None = None) -> list[dict[str, Any]]:
        """Retrieve industry-specific profiles."""
        if industry:
            return self.query_by_type("industry_profile", industry=industry)
        return self.query_by_type("industry_profile")

    def query_jurisdiction_rules(self, territory: str | None = None) -> list[dict[str, Any]]:
        """Retrieve jurisdiction-specific compliance rules."""
        if territory:
            return self.query_by_type("jurisdiction_rule", territory=territory)
        return self.query_by_type("jurisdiction_rule")

    def query_products(self, lob: str | None = None) -> list[dict[str, Any]]:
        """Retrieve product definitions, optionally filtered by LOB."""
        if lob:
            return self.query_by_type("product", line_of_business=lob)
        return self.query_by_type("product")

    def query_regulatory(self, jurisdiction: str) -> list[dict[str, Any]]:
        """Retrieve regulatory requirements for a jurisdiction."""
        return self.query_by_type("regulatory", jurisdiction=jurisdiction)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

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
