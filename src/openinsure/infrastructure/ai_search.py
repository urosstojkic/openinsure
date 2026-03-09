"""Azure AI Search adapter for hybrid vector + keyword search.

Supports document indexing, hybrid queries (vector + BM25), deletion,
and filtering / faceting.  Authentication uses ``DefaultAzureCredential``.
"""

from __future__ import annotations

from typing import Any

import structlog
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient, SearchItemPaged
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

logger = structlog.get_logger()


class SearchAdapter:
    """Async-style adapter for Azure AI Search with hybrid retrieval.

    Parameters
    ----------
    endpoint:
        AI Search service endpoint, e.g. ``https://mysearch.search.windows.net``.
    index_name:
        Name of the target search index.
    credential:
        Azure credential.  Defaults to ``DefaultAzureCredential``.
    embedding_dimensions:
        Dimensionality of the embedding vectors (default 1536 for
        ``text-embedding-ada-002``).
    """

    def __init__(
        self,
        endpoint: str,
        index_name: str,
        *,
        credential: DefaultAzureCredential | None = None,
        embedding_dimensions: int = 1536,
    ) -> None:
        self._endpoint = endpoint
        self._index_name = index_name
        self._credential = credential or DefaultAzureCredential()
        self._embedding_dimensions = embedding_dimensions

        self._index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=self._credential,
        )
        self._search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=self._credential,
        )

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    async def ensure_index(self) -> None:
        """Create or update the search index with vector support."""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="last_updated", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self._embedding_dimensions,
                vector_search_profile_name="default-profile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
            profiles=[
                VectorSearchProfile(
                    name="default-profile",
                    algorithm_configuration_name="default-hnsw",
                )
            ],
        )

        index = SearchIndex(
            name=self._index_name,
            fields=fields,
            vector_search=vector_search,
        )
        self._index_client.create_or_update_index(index)
        logger.info("ai_search.index_ensured", index=self._index_name)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_document(
        self,
        document_id: str,
        content: str,
        *,
        title: str = "",
        source: str = "",
        category: str = "",
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Index (upsert) a document with optional vector embedding.

        Parameters
        ----------
        document_id:
            Unique document key.
        content:
            Full-text content for keyword search.
        title:
            Document title (filterable).
        source:
            Source identifier (filterable, facetable).
        category:
            Category label (filterable, facetable).
        embedding:
            Pre-computed vector embedding for hybrid search.
        metadata:
            Additional key-value pairs stored alongside the document.
        """
        doc: dict[str, Any] = {
            "id": document_id,
            "content": content,
            "title": title,
            "source": source,
            "category": category,
        }
        if embedding:
            doc["content_vector"] = embedding
        if metadata:
            doc.update(metadata)

        result = self._search_client.upload_documents(documents=[doc])
        succeeded = result[0].succeeded if result else False
        logger.info(
            "ai_search.document_indexed",
            document_id=document_id,
            succeeded=succeeded,
        )
        return {"document_id": document_id, "succeeded": succeeded}

    async def index_documents_batch(
        self,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Batch-index multiple documents."""
        results = self._search_client.upload_documents(documents=documents)
        outcomes = [{"key": r.key, "succeeded": r.succeeded, "error": r.error_message} for r in results]
        logger.info("ai_search.batch_indexed", count=len(documents))
        return outcomes

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        vector: list[float] | None = None,
        top: int = 10,
        filters: str | None = None,
        facets: list[str] | None = None,
        select: list[str] | None = None,
        semantic_configuration: str | None = None,
    ) -> dict[str, Any]:
        """Execute a hybrid (vector + keyword) search.

        Parameters
        ----------
        query:
            Free-text query for BM25 ranking.
        vector:
            Optional embedding vector for vector search.
        top:
            Maximum results to return.
        filters:
            OData ``$filter`` expression, e.g. ``"category eq 'product'"``.
        facets:
            List of fields to return facet counts for.
        select:
            Fields to include in results (default: all).
        semantic_configuration:
            Name of the semantic configuration to use for re-ranking.
        """
        vector_queries = None
        if vector:
            vector_queries = [
                VectorizedQuery(
                    vector=vector,
                    k_nearest_neighbors=top,
                    fields="content_vector",
                )
            ]

        search_results: SearchItemPaged = self._search_client.search(
            search_text=query if query else "*",
            vector_queries=vector_queries,
            top=top,
            filter=filters,
            facets=facets,
            select=select,
            query_type="semantic" if semantic_configuration else "simple",
            semantic_configuration_name=semantic_configuration,
        )

        hits: list[dict[str, Any]] = []
        for result in search_results:
            hit = dict(result)
            hit.pop("content_vector", None)  # exclude large vectors from response
            hits.append(hit)

        facet_results: dict[str, Any] = {}
        if hasattr(search_results, "get_facets"):
            raw_facets = search_results.get_facets()
            if raw_facets:
                facet_results = {
                    field: [{"value": f["value"], "count": f["count"]} for f in values]
                    for field, values in raw_facets.items()
                }

        logger.debug(
            "ai_search.search_executed",
            query=query[:80],
            result_count=len(hits),
        )
        return {"results": hits, "facets": facet_results, "count": len(hits)}

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the index by ID."""
        result = self._search_client.delete_documents(documents=[{"id": document_id}])
        succeeded = result[0].succeeded if result else False
        logger.info(
            "ai_search.document_deleted",
            document_id=document_id,
            succeeded=succeeded,
        )
        return succeeded

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close underlying clients."""
        self._search_client.close()
        self._index_client.close()
        logger.info("ai_search.closed")
