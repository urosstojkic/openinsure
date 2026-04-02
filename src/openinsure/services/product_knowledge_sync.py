"""Product → Knowledge pipeline: SQL products ➜ Cosmos DB ➜ AI Search.

This service ensures that every product created, updated, published, or retired
in the Product Management system is automatically reflected in the knowledge
stores that Foundry agents query.  The flow is:

    Product API (SQL) ──sync──▸ Cosmos DB  ──sync──▸ AI Search  ──tool──▸ Agents
                                (source of truth)     (agent retrieval)

Design principles:
  1. **Non-blocking** — sync runs as a background task; API latency is unaffected.
  2. **Idempotent** — calling sync(product) twice with the same data is safe.
  3. **Fail-open** — if Cosmos or Search is unavailable, the product API still works.
     Failures are logged and can be retried via the ``/admin/sync-products`` endpoint.
  4. **Structured for agents** — the knowledge document is formatted so that
     triage, underwriting, and rating agents can immediately use coverages,
     appetite rules, rating factors, and authority limits.
  5. **Lifecycle-aware** — retired products are removed from the search index so
     agents don't quote against sunset products.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

# Maximum retries for transient failures
_MAX_RETRIES = 2


class SyncResult:
    """Outcome of a single product sync operation."""

    __slots__ = ("cosmos_ok", "error", "product_code", "product_id", "search_ok")

    def __init__(self, product_id: str, product_code: str = "") -> None:
        self.product_id = product_id
        self.product_code = product_code
        self.cosmos_ok: bool = False
        self.search_ok: bool = False
        self.error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_code": self.product_code,
            "cosmos": "ok" if self.cosmos_ok else "failed",
            "search": "ok" if self.search_ok else "failed",
            "error": self.error,
        }


def _product_to_knowledge_document(
    product: dict[str, Any],
    *,
    relational_coverages: list[dict[str, Any]] | None = None,
    relational_factors: list[dict[str, Any]] | None = None,
    relational_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Convert a SQL product record into a structured knowledge document.

    The document is formatted so that Foundry agents can parse it to:
    - Check appetite rules during triage
    - Retrieve coverage definitions during underwriting
    - Look up rating factors during premium calculation
    - Enforce authority limits during binding decisions

    **v106 (#164):** When *relational_coverages*, *relational_factors*, or
    *relational_rules* are provided (from the normalised tables), they take
    precedence over the JSON blob fields.  This gives properly typed,
    indexed data instead of parsed JSON.
    """
    code = product.get("code", product.get("product_code", ""))
    name = product.get("name", product.get("product_name", ""))
    lob = product.get("line_of_business", product.get("product_line", ""))
    status = product.get("status", "draft")

    # Prefer relational data when available, fall back to JSON blob
    coverages = relational_coverages if relational_coverages else product.get("coverages", [])
    rating_factors = relational_factors if relational_factors else product.get("rating_factors", [])
    appetite_rules = relational_rules if relational_rules else product.get("appetite_rules", [])

    # Build a rich text representation for keyword search
    coverage_text = ""
    if coverages:
        lines = []
        for c in coverages:
            cname = c.get("name", c.get("coverage_name", ""))
            limit = c.get("default_limit", 0)
            deductible = c.get("default_deductible", 0)
            lines.append(f"  - {cname}: limit ${limit:,.0f}, deductible ${deductible:,.0f}")
        coverage_text = "Coverages:\n" + "\n".join(lines)

    rating_text = ""
    if rating_factors:
        lines = []
        for rf in rating_factors:
            fname = rf.get("name", rf.get("factor_name", ""))
            ftype = rf.get("type", rf.get("factor_type", ""))
            weight = rf.get("weight", 0)
            lines.append(f"  - {fname} ({ftype}, weight={weight})")
        rating_text = "Rating Factors:\n" + "\n".join(lines)

    appetite_text = ""
    if appetite_rules:
        lines = []
        for rule in appetite_rules:
            field = rule.get("field", "")
            op = rule.get("operator", "")
            val = rule.get("value", "")
            lines.append(f"  - {field} {op} {val}")
        appetite_text = "Appetite Rules:\n" + "\n".join(lines)

    authority = product.get("authority_limits", {}) or {}
    authority_text = ""
    if authority:
        auto_bind = authority.get("auto_bind_max", authority.get("max_auto_bind_premium", 0))
        senior = authority.get("senior_uw_max", authority.get("requires_senior_review_above", 0))
        authority_text = f"Authority Limits: auto-bind up to ${auto_bind:,.0f}, senior UW review above ${senior:,.0f}"

    territories = product.get("territories", [])
    territory_text = f"Territories: {', '.join(territories)}" if territories else ""

    metadata = product.get("metadata", {}) or {}
    meta_text = ""
    if metadata:
        parts = [f"{k}={v}" for k, v in metadata.items()]
        meta_text = f"Product Metadata: {', '.join(parts)}"

    # Assemble full-text content
    content_parts = [
        f"PRODUCT: {name} ({code})",
        f"Line of Business: {lob}",
        f"Status: {status}",
        f"Version: {product.get('version', '1')}",
        f"Description: {product.get('description', '')}",
        coverage_text,
        rating_text,
        appetite_text,
        authority_text,
        territory_text,
        meta_text,
    ]
    content = "\n".join(part for part in content_parts if part)

    # Structured JSON for direct consumption by agents
    structured = {
        "code": code,
        "name": name,
        "line_of_business": lob,
        "status": status,
        "version": str(product.get("version", "1")),
        "description": product.get("description", ""),
        "coverages": coverages,
        "rating_factors": rating_factors,
        "appetite_rules": appetite_rules,
        "authority_limits": authority,
        "territories": territories,
        "metadata": metadata,
    }

    return {
        "id": f"product-{code or product.get('id', '')}",
        "content": content,
        "structured": structured,
        "category": "product",
        "source": "product-management",
        "tags": ["product", lob, status, code],
        "last_updated": datetime.now(UTC).isoformat(),
    }


class ProductKnowledgeSyncService:
    """Synchronises product definitions from SQL to Cosmos DB and AI Search.

    Usage::

        svc = ProductKnowledgeSyncService()
        result = await svc.sync_product(product_dict)
        results = await svc.sync_all_products()
        ok = await svc.remove_product(product_id)
    """

    def __init__(self) -> None:
        self._cosmos = None
        self._search = None
        self._initialised = False

    def _init_clients(self) -> None:
        """Lazy-init Cosmos and Search clients (avoids import-time failures)."""
        if self._initialised:
            return
        self._initialised = True

        from openinsure.config import get_settings

        settings = get_settings()

        # Cosmos DB client
        if settings.cosmos_endpoint:
            try:
                from azure.cosmos import CosmosClient
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
                client = CosmosClient(settings.cosmos_endpoint, credential=credential)
                db = client.get_database_client(settings.cosmos_database_name or "openinsure-knowledge")
                # Ensure products container exists
                with contextlib.suppress(Exception):
                    db.create_container_if_not_exists(
                        id="products",
                        partition_key={"paths": ["/category"], "kind": "Hash"},
                    )
                self._cosmos = db
                logger.info("product_sync.cosmos_connected")
            except Exception:
                logger.warning("product_sync.cosmos_unavailable", exc_info=True)

        # AI Search client
        if settings.search_endpoint:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.search.documents import SearchClient

                credential = DefaultAzureCredential()
                self._search = SearchClient(
                    endpoint=settings.search_endpoint,
                    index_name=settings.search_index_name or "openinsure-knowledge",
                    credential=credential,
                )
                logger.info("product_sync.search_connected")
            except Exception:
                logger.warning("product_sync.search_unavailable", exc_info=True)

    # ------------------------------------------------------------------
    # Single product sync
    # ------------------------------------------------------------------

    async def sync_product(self, product: dict[str, Any]) -> dict[str, Any]:
        """Sync a single product to Cosmos DB and AI Search.

        Returns a dict with sync status for each destination.

        **v106 (#164):** loads relational data from ``ProductRelationsRepository``
        when available, building richer knowledge documents from properly
        typed, indexed columns instead of parsing JSON blobs.
        """
        self._init_clients()
        code = product.get("code", product.get("product_code", str(product.get("id", ""))))
        result = SyncResult(str(product.get("id", "")), code)

        # Load relational data when available (Phase 3c, #164)
        rel_coverages: list[dict[str, Any]] | None = None
        rel_factors: list[dict[str, Any]] | None = None
        rel_rules: list[dict[str, Any]] | None = None
        try:
            from openinsure.infrastructure.factory import get_product_relations_repository

            relations = get_product_relations_repository()
            if relations is not None:
                product_id = str(product.get("id", ""))
                if product_id:
                    rel_coverages = await relations.get_coverages(product_id) or None
                    rel_factors = await relations.get_rating_factors(product_id) or None
                    rel_rules = await relations.get_appetite_rules(product_id) or None
        except Exception:
            logger.debug("product_sync.relational_load_failed", product_code=code, exc_info=True)

        doc = _product_to_knowledge_document(
            product,
            relational_coverages=rel_coverages,
            relational_factors=rel_factors,
            relational_rules=rel_rules,
        )

        # 1. Cosmos DB — source of truth for knowledge
        if self._cosmos is not None:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    container = self._cosmos.get_container_client("products")
                    cosmos_doc = {
                        "id": doc["id"],
                        "category": "product",
                        "code": code,
                        "content": doc["content"],
                        "structured": doc["structured"],
                        "source": "product-management",
                        "last_updated": doc["last_updated"],
                    }
                    container.upsert_item(cosmos_doc)
                    result.cosmos_ok = True
                    break
                except Exception:
                    if attempt == _MAX_RETRIES:
                        logger.warning(
                            "product_sync.cosmos_write_failed",
                            product_code=code,
                            attempt=attempt,
                            exc_info=True,
                        )
                    # Brief backoff
                    import asyncio

                    await asyncio.sleep(0.5 * (attempt + 1))

        # 2. AI Search — for agent retrieval via search tool
        if self._search is None:
            logger.warning(
                "product_sync.search_client_unavailable",
                product_code=code,
                reason="AI Search client not initialised — check SEARCH_ENDPOINT config",
            )
        else:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    # Field names must match the AI Search index schema:
                    # id, content, title, source, category, last_updated
                    search_doc = {
                        "id": doc["id"],
                        "content": doc["content"] + "\n\n" + json.dumps(doc["structured"], default=str),
                        "title": f"{doc['structured'].get('name', '')} ({code})",
                        "category": "product",
                        "source": "product-management",
                        "last_updated": doc["last_updated"],
                    }
                    logger.info(
                        "product_sync.search_upload_attempt",
                        product_code=code,
                        attempt=attempt,
                        doc_id=search_doc["id"],
                        doc_keys=list(search_doc.keys()),
                        content_length=len(search_doc.get("content", "")),
                    )
                    upload_result = self._search.upload_documents(documents=[search_doc])
                    result.search_ok = upload_result[0].succeeded if upload_result else False
                    if not result.search_ok and upload_result:
                        err_msg = getattr(upload_result[0], "error_message", None)
                        status_code = getattr(upload_result[0], "status_code", None)
                        logger.warning(
                            "product_sync.search_upload_rejected",
                            product_code=code,
                            error=err_msg,
                            status_code=status_code,
                            key=getattr(upload_result[0], "key", None),
                            succeeded=getattr(upload_result[0], "succeeded", None),
                        )
                    if result.search_ok:
                        break
                except Exception as exc:
                    logger.warning(
                        "product_sync.search_write_failed",
                        product_code=code,
                        attempt=attempt,
                        error_type=type(exc).__name__,
                        error_detail=str(exc)[:500],
                        exc_info=True,
                    )
                    import asyncio

                    await asyncio.sleep(0.5 * (attempt + 1))

        if not result.cosmos_ok and not result.search_ok:
            result.error = "Both Cosmos and Search sync failed"
        elif not result.cosmos_ok:
            result.error = "Cosmos sync failed (Search succeeded)"
        elif not result.search_ok:
            result.error = "Search sync failed (Cosmos succeeded)"

        return result.to_dict()

    # ------------------------------------------------------------------
    # Remove product from knowledge (on retire/delete)
    # ------------------------------------------------------------------

    async def remove_product(self, product_id: str) -> bool:
        """Remove a product from Cosmos DB and AI Search.

        Called when a product is retired or deleted — agents should no longer
        see it in search results.
        """
        self._init_clients()
        removed_any = False

        # Try to find the document ID (product-{code})
        doc_id = f"product-{product_id}"

        if self._cosmos is not None:
            try:
                container = self._cosmos.get_container_client("products")
                # Try reading first to get the actual doc_id
                items = list(
                    container.query_items(
                        query="SELECT * FROM c WHERE c.id = @id OR CONTAINS(c.id, @pid)",
                        parameters=[
                            {"name": "@id", "value": doc_id},
                            {"name": "@pid", "value": product_id},
                        ],
                        enable_cross_partition_query=True,
                    )
                )
                for item in items:
                    container.delete_item(item["id"], partition_key=item.get("category", "product"))
                    removed_any = True
                    logger.info("product_sync.cosmos_removed", doc_id=item["id"])
            except Exception:
                logger.warning("product_sync.cosmos_remove_failed", product_id=product_id, exc_info=True)

        if self._search is not None:
            try:
                self._search.delete_documents(documents=[{"id": doc_id}])
                removed_any = True
                logger.info("product_sync.search_removed", doc_id=doc_id)
            except Exception:
                logger.warning("product_sync.search_remove_failed", product_id=product_id, exc_info=True)

        return removed_any

    # ------------------------------------------------------------------
    # Bulk sync — all products from SQL
    # ------------------------------------------------------------------

    async def sync_all_products(self) -> dict[str, Any]:
        """Sync ALL products from SQL to Cosmos DB and AI Search.

        Used for initial seeding, disaster recovery, or after infrastructure changes.
        """
        from openinsure.infrastructure.factory import get_product_repository

        repo = get_product_repository()
        products = await repo.list_all(skip=0, limit=1000)

        results: list[dict[str, Any]] = []
        cosmos_ok = 0
        search_ok = 0
        errors = 0

        for product in products:
            result = await self.sync_product(product)
            results.append(result)
            if result.get("cosmos") == "ok":
                cosmos_ok += 1
            if result.get("search") == "ok":
                search_ok += 1
            if result.get("error"):
                errors += 1

        summary = {
            "total_products": len(products),
            "cosmos_synced": cosmos_ok,
            "search_synced": search_ok,
            "errors": errors,
            "details": results,
        }
        logger.info("product_sync.bulk_complete", **{k: v for k, v in summary.items() if k != "details"})
        return summary
