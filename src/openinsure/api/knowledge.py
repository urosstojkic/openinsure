"""Knowledge graph API endpoints for OpenInsure.

Exposes the insurance knowledge graph (underwriting guidelines,
product definitions, regulatory requirements) stored in Cosmos DB.
Falls back to the rich in-memory knowledge store when Cosmos DB is
not configured — guaranteeing agents always have comprehensive context.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_in_memory_knowledge_store, get_knowledge_store

router = APIRouter()
_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class KnowledgeSearchResult(BaseModel):
    """Single search hit from the knowledge graph."""

    id: str
    entityType: str = ""
    category: str = ""
    content: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Search results."""

    query: str
    entity_type: str | None = None
    results: list[KnowledgeSearchResult]
    total: int


class GuidelineResponse(BaseModel):
    """Underwriting guidelines for a line of business."""

    lob: str
    guidelines: list[dict[str, Any]]
    total: int


class RatingFactorsResponse(BaseModel):
    """Rating factor tables for a line of business."""

    lob: str
    rating_factors: dict[str, Any]


class CoverageOptionsResponse(BaseModel):
    """Available coverage options for a line of business."""

    lob: str
    coverage_options: list[dict[str, Any]]
    total: int


class KnowledgeProductResponse(BaseModel):
    """Product definitions from the knowledge graph."""

    products: list[dict[str, Any]]
    total: int


class ClaimsPrecedentResponse(BaseModel):
    """Claims precedents for adjuster guidance."""

    claim_type: str
    precedents: list[dict[str, Any]]
    total: int


class ComplianceRulesResponse(BaseModel):
    """Compliance framework rules."""

    framework: str
    rules: list[dict[str, Any]]
    total: int


# ---------------------------------------------------------------------------
# Static product data (retained for /products endpoint)
# ---------------------------------------------------------------------------

_COSMOS_META_KEYS = frozenset({"_rid", "_self", "_etag", "_attachments", "_ts"})

_STATIC_PRODUCTS: list[dict[str, Any]] = [
    {
        "id": "product-cyber-smb",
        "entityType": "product",
        "code": "cyber-smb",
        "name": "Cyber Liability – SMB",
        "line_of_business": "cyber",
    },
]


# ---------------------------------------------------------------------------
# Helper: get data from Cosmos or in-memory store
# ---------------------------------------------------------------------------


def _mem_store():
    return get_in_memory_knowledge_store()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_endpoint(
    q: str = Query(..., min_length=1, description="Search query text"),
    type: str | None = Query(None, description="Filter by entity type"),
) -> KnowledgeSearchResponse:
    """Search the knowledge base by text, optionally filtered by entity type."""
    try:
        store = get_knowledge_store()
        if store:
            raw = store.search_knowledge(q, entity_type=type)
            results = [
                KnowledgeSearchResult(
                    id=doc.get("id", ""),
                    entityType=doc.get("entityType", ""),
                    content=doc.get("content", ""),
                    extra={
                        k: v
                        for k, v in doc.items()
                        if k not in ("id", "entityType", "content") and k not in _COSMOS_META_KEYS
                    },
                )
                for doc in raw
            ]
            return KnowledgeSearchResponse(query=q, entity_type=type, results=results, total=len(results))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable", resource="search", exc_info=True)

    # Rich in-memory fallback
    mem = _mem_store()
    hits = mem.search(q)
    if type:
        hits = [h for h in hits if h.get("category") == type]
    results = [
        KnowledgeSearchResult(
            id=h["id"],
            category=h.get("category", ""),
            entityType=h.get("category", ""),
            content=h.get("match_context", ""),
            extra=h.get("data", {}),
        )
        for h in hits
    ]
    return KnowledgeSearchResponse(query=q, entity_type=type, results=results, total=len(results))


@router.get("/guidelines/{lob}", response_model=GuidelineResponse)
async def get_guidelines(lob: str) -> GuidelineResponse:
    """Retrieve underwriting guidelines for a line of business."""
    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_guidelines(lob)
            if docs:
                return GuidelineResponse(lob=lob, guidelines=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable lob=%s", lob, exc_info=True)

    # In-memory fallback with rich data
    mem = _mem_store()
    gl = mem.get_guidelines(lob)
    if gl is None:
        raise HTTPException(status_code=404, detail=f"No guidelines found for LOB: {lob}")
    return GuidelineResponse(lob=lob, guidelines=[gl], total=1)


@router.get("/rating-factors/{lob}", response_model=RatingFactorsResponse)
async def get_rating_factors(lob: str) -> RatingFactorsResponse:
    """Retrieve rating factor tables for a line of business."""
    mem = _mem_store()
    rf = mem.get_rating_factors(lob)
    if rf is None:
        raise HTTPException(status_code=404, detail=f"No rating factors found for LOB: {lob}")
    return RatingFactorsResponse(lob=lob, rating_factors=rf)


@router.get("/coverage-options/{lob}", response_model=CoverageOptionsResponse)
async def get_coverage_options(lob: str) -> CoverageOptionsResponse:
    """Retrieve available coverage options for a line of business."""
    mem = _mem_store()
    opts = mem.get_coverage_options(lob)
    if opts is None:
        raise HTTPException(status_code=404, detail=f"No coverage options found for LOB: {lob}")
    return CoverageOptionsResponse(lob=lob, coverage_options=opts, total=len(opts))


@router.put("/guidelines/{lob}", response_model=GuidelineResponse)
async def update_guidelines(lob: str, body: dict[str, Any]) -> GuidelineResponse:
    """Update underwriting guidelines for a line of business (Product Manager role)."""
    mem = _mem_store()
    updated = mem.update_guidelines(lob, body)
    _log.info("knowledge.guidelines_updated", lob=lob)
    return GuidelineResponse(lob=lob, guidelines=[updated], total=1)


@router.get("/products", response_model=KnowledgeProductResponse)
async def list_knowledge_products(
    lob: str | None = Query(None, description="Filter by line of business"),
) -> KnowledgeProductResponse:
    """List product definitions from the knowledge graph."""
    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_products(lob)
            if docs:
                return KnowledgeProductResponse(products=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=products", exc_info=True)

    products = _STATIC_PRODUCTS
    if lob:
        products = [p for p in products if p.get("line_of_business") == lob]
    return KnowledgeProductResponse(products=products, total=len(products))


# ---------------------------------------------------------------------------
# Claims precedents & compliance rules endpoints
# ---------------------------------------------------------------------------


@router.get("/claims-precedents/{claim_type}", response_model=ClaimsPrecedentResponse)
async def get_claims_precedents(claim_type: str) -> ClaimsPrecedentResponse:
    """Retrieve claims precedents by claim type for adjuster guidance."""
    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("claims_precedent")
            docs = [d for d in docs if d.get("claim_type") == claim_type]
            if docs:
                return ClaimsPrecedentResponse(claim_type=claim_type, precedents=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=claims_precedents", exc_info=True)

    mem = _mem_store()
    precedent = mem.get_claims_precedents(claim_type)
    if precedent is None:
        raise HTTPException(status_code=404, detail=f"No precedents for claim type: {claim_type}")
    return ClaimsPrecedentResponse(claim_type=claim_type, precedents=[precedent], total=1)


@router.get("/claims-precedents", response_model=ClaimsPrecedentResponse)
async def list_claims_precedents() -> ClaimsPrecedentResponse:
    """List all claims precedents."""
    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("claims_precedent")
            if docs:
                return ClaimsPrecedentResponse(claim_type="all", precedents=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=claims_precedents", exc_info=True)

    mem = _mem_store()
    all_prec = mem.list_claims_precedents()
    return ClaimsPrecedentResponse(claim_type="all", precedents=list(all_prec.values()), total=len(all_prec))


@router.get("/compliance-rules/{framework}", response_model=ComplianceRulesResponse)
async def get_compliance_rules(framework: str) -> ComplianceRulesResponse:
    """Retrieve compliance framework rules."""
    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("compliance_rule")
            docs = [d for d in docs if d.get("framework") == framework]
            if docs:
                return ComplianceRulesResponse(framework=framework, rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=compliance_rules", exc_info=True)

    mem = _mem_store()
    rules = mem.get_compliance_rules(framework)
    if rules is None:
        raise HTTPException(status_code=404, detail=f"No rules for framework: {framework}")
    return ComplianceRulesResponse(framework=framework, rules=[rules], total=1)


@router.get("/compliance-rules", response_model=ComplianceRulesResponse)
async def list_compliance_rules() -> ComplianceRulesResponse:
    """List all compliance framework rules."""
    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("compliance_rule")
            if docs:
                return ComplianceRulesResponse(framework="all", rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=compliance_rules", exc_info=True)

    mem = _mem_store()
    all_rules = mem.list_compliance_rules()
    return ComplianceRulesResponse(framework="all", rules=list(all_rules.values()), total=len(all_rules))
