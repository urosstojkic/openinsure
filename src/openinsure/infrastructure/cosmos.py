"""Azure Cosmos DB Gremlin (graph) adapter for the OpenInsure knowledge graph.

Uses the Gremlin Python driver to communicate with the Cosmos DB Gremlin API.
Authentication is handled via ``DefaultAzureCredential`` where supported,
with a fallback to primary-key auth for local development.
"""

from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from azure.identity import DefaultAzureCredential
from gremlin_python.driver import client as gremlin_client
from gremlin_python.driver import serializer

logger = structlog.get_logger()


class CosmosGraphAdapter:
    """Async wrapper for Cosmos DB Gremlin operations.

    Parameters
    ----------
    endpoint:
        Cosmos DB Gremlin endpoint, e.g.
        ``wss://myaccount.gremlin.cosmos.azure.com:443/``.
    database:
        Database name.
    graph:
        Graph (container) name.
    primary_key:
        Account primary key.  If *None*, ``DefaultAzureCredential`` is used.
    credential:
        Optional explicit Azure credential.
    pool_size:
        Thread-pool size for blocking Gremlin I/O.
    """

    def __init__(
        self,
        endpoint: str,
        database: str,
        graph: str,
        *,
        primary_key: str | None = None,
        credential: DefaultAzureCredential | None = None,
        pool_size: int = 4,
    ) -> None:
        self._endpoint = endpoint
        self._database = database
        self._graph = graph
        self._executor = ThreadPoolExecutor(max_workers=pool_size)

        if primary_key:
            password = primary_key
        else:
            cred = credential or DefaultAzureCredential()
            token = cred.get_token("https://cosmos.azure.com/.default")
            password = token.token

        self._client = gremlin_client.Client(
            url=endpoint,
            traversal_source="g",
            username=f"/dbs/{database}/colls/{graph}",
            password=password,
            message_serializer=serializer.GraphSONSerializersV2d0(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run(self, fn, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, functools.partial(fn, *args, **kwargs))

    def _submit(self, query: str, bindings: dict[str, Any] | None = None) -> list[Any]:
        result_set = self._client.submit(query, bindings or {})
        return result_set.all().result()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_vertex(
        self,
        label: str,
        vertex_id: str,
        properties: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Add a vertex to the graph.

        Parameters
        ----------
        label:
            Vertex label (e.g. ``"product"``, ``"coverage"``).
        vertex_id:
            Unique vertex identifier (used as partition key in Cosmos DB).
        properties:
            Optional property map.
        """
        props = properties or {}
        prop_clause = "".join(f".property('{k}', {k})" for k in props)
        query = f"g.addV('{label}').property('id', id).property('partitionKey', pk){prop_clause}"
        bindings: dict[str, Any] = {"id": vertex_id, "pk": vertex_id, **props}

        result = await self._run(self._submit, query, bindings)
        logger.info("cosmos.vertex_added", label=label, vertex_id=vertex_id)
        return result

    async def add_edge(
        self,
        label: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Add a directed edge between two vertices."""
        props = properties or {}
        prop_clause = "".join(f".property('{k}', {k})" for k in props)
        query = f"g.V(from_id).addE('{label}').to(g.V(to_id)){prop_clause}"
        bindings: dict[str, Any] = {"from_id": from_id, "to_id": to_id, **props}

        result = await self._run(self._submit, query, bindings)
        logger.info("cosmos.edge_added", label=label, from_id=from_id, to_id=to_id)
        return result

    async def query(
        self,
        gremlin_query: str,
        bindings: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Execute an arbitrary Gremlin traversal query."""
        result = await self._run(self._submit, gremlin_query, bindings)
        logger.debug("cosmos.query_executed", result_count=len(result) if result else 0)
        return result

    async def traverse(
        self,
        start_vertex_id: str,
        edge_label: str | None = None,
        direction: str = "out",
        depth: int = 1,
    ) -> list[Any]:
        """Traverse the graph from a starting vertex.

        Parameters
        ----------
        start_vertex_id:
            ID of the vertex to start from.
        edge_label:
            Optional edge label filter.
        direction:
            ``"out"`` (default), ``"in"``, or ``"both"``.
        depth:
            Number of hops.
        """
        dir_step = {"out": "out", "in": "in_", "both": "both"}.get(direction, "out")
        edge_filter = f"'{edge_label}'" if edge_label else ""
        step = f".{dir_step}({edge_filter})" * depth
        query = f"g.V(start_id){step}.valueMap(true)"
        bindings = {"start_id": start_vertex_id}

        result = await self._run(self._submit, query, bindings)
        logger.debug(
            "cosmos.traverse",
            start=start_vertex_id,
            depth=depth,
            results=len(result) if result else 0,
        )
        return result

    async def close(self) -> None:
        """Close the Gremlin client and thread pool."""
        self._client.close()
        self._executor.shutdown(wait=False)
        logger.info("cosmos.closed")
