"""Knowledge graph API endpoints for OpenInsure.

Exposes the insurance knowledge graph (underwriting guidelines,
product definitions, regulatory requirements) stored in Cosmos DB.
Falls back to the static dictionaries when Cosmos DB is not configured.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_knowledge_store

router = APIRouter()
_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class KnowledgeSearchResult(BaseModel):
    """Single search hit from the knowledge graph."""

    id: str
    entityType: str
    content: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Search results."""

    query: str
    entity_type: str | None
    results: list[KnowledgeSearchResult]
    total: int


class GuidelineResponse(BaseModel):
    """Underwriting guidelines for a line of business."""

    lob: str
    guidelines: list[dict[str, Any]]
    total: int


class KnowledgeProductResponse(BaseModel):
    """Product definitions from the knowledge graph."""

    products: list[dict[str, Any]]
    total: int


# ---------------------------------------------------------------------------
# Static fallback data (mirrors KnowledgeAgent dictionaries)
# ---------------------------------------------------------------------------

_COSMOS_META_KEYS = frozenset({"_rid", "_self", "_etag", "_attachments", "_ts"})

_STATIC_GUIDELINES: dict[str, dict[str, Any]] = {
    "cyber": {
        "lob": "cyber",
        "min_revenue": "1000000",
        "max_revenue": "5000000000",
        "excluded_industries": ["banking", "gambling"],
        "required_controls": [
            "mfa",
            "endpoint_protection",
            "backup_strategy",
            "incident_response_plan",
        ],
        "max_prior_incidents": 5,
        "authority_tiers": {
            "auto_bind": "500000",
            "senior_underwriter": "2000000",
            "committee": "10000000",
        },
        "minimum_premium": "5000",
    },
    "general_liability": {
        "lob": "general_liability",
        "min_revenue": "500000",
        "max_revenue": "2000000000",
        "excluded_industries": [],
        "required_controls": [],
        "authority_tiers": {
            "auto_bind": "250000",
            "senior_underwriter": "1000000",
            "committee": "5000000",
        },
        "minimum_premium": "2500",
    },
    "property": {
        "lob": "property",
        "min_insured_value": "100000",
        "max_insured_value": "500000000",
        "excluded_industries": [],
        "required_controls": ["sprinkler_system"],
        "authority_tiers": {
            "auto_bind": "1000000",
            "senior_underwriter": "5000000",
            "committee": "25000000",
        },
        "minimum_premium": "3000",
    },
}

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

    # Static fallback — simple substring match
    results = []
    for lob, gl in _STATIC_GUIDELINES.items():
        if q.lower() in str(gl).lower():
            if type and type != "guideline":
                continue
            results.append(KnowledgeSearchResult(id=f"guideline-{lob}", entityType="guideline", content=str(gl)))
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

    # Static fallback
    gl = _STATIC_GUIDELINES.get(lob)
    if gl is None:
        raise HTTPException(status_code=404, detail=f"No guidelines found for LOB: {lob}")
    return GuidelineResponse(lob=lob, guidelines=[gl], total=1)


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

    # Static fallback
    products = _STATIC_PRODUCTS
    if lob:
        products = [p for p in products if p.get("line_of_business") == lob]
    return KnowledgeProductResponse(products=products, total=len(products))


# ---------------------------------------------------------------------------
# Claims precedents & compliance rules endpoints
# ---------------------------------------------------------------------------


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


@router.get("/claims-precedents/{claim_type}", response_model=ClaimsPrecedentResponse)
async def get_claims_precedents(claim_type: str) -> ClaimsPrecedentResponse:
    """Retrieve claims precedents by claim type for adjuster guidance."""
    from openinsure.agents.knowledge_agent import CLAIMS_PRECEDENTS

    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("claims_precedent")
            docs = [d for d in docs if d.get("claim_type") == claim_type]
            if docs:
                return ClaimsPrecedentResponse(claim_type=claim_type, precedents=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=claims_precedents", exc_info=True)

    precedent = CLAIMS_PRECEDENTS.get(claim_type)
    if precedent is None:
        raise HTTPException(status_code=404, detail=f"No precedents for claim type: {claim_type}")
    return ClaimsPrecedentResponse(claim_type=claim_type, precedents=[precedent], total=1)


@router.get("/claims-precedents", response_model=ClaimsPrecedentResponse)
async def list_claims_precedents() -> ClaimsPrecedentResponse:
    """List all claims precedents."""
    from openinsure.agents.knowledge_agent import CLAIMS_PRECEDENTS

    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("claims_precedent")
            if docs:
                return ClaimsPrecedentResponse(claim_type="all", precedents=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=claims_precedents", exc_info=True)

    return ClaimsPrecedentResponse(
        claim_type="all", precedents=list(CLAIMS_PRECEDENTS.values()), total=len(CLAIMS_PRECEDENTS)
    )


@router.get("/compliance-rules/{framework}", response_model=ComplianceRulesResponse)
async def get_compliance_rules(framework: str) -> ComplianceRulesResponse:
    """Retrieve compliance framework rules."""
    from openinsure.agents.knowledge_agent import COMPLIANCE_RULES

    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("compliance_rule")
            docs = [d for d in docs if d.get("framework") == framework]
            if docs:
                return ComplianceRulesResponse(framework=framework, rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=compliance_rules", exc_info=True)

    rules = COMPLIANCE_RULES.get(framework)
    if rules is None:
        raise HTTPException(status_code=404, detail=f"No rules for framework: {framework}")
    return ComplianceRulesResponse(framework=framework, rules=[rules], total=1)


@router.get("/compliance-rules", response_model=ComplianceRulesResponse)
async def list_compliance_rules() -> ComplianceRulesResponse:
    """List all compliance framework rules."""
    from openinsure.agents.knowledge_agent import COMPLIANCE_RULES

    try:
        store = get_knowledge_store()
        if store:
            docs = store.query_by_type("compliance_rule")
            if docs:
                return ComplianceRulesResponse(framework="all", rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=compliance_rules", exc_info=True)

    return ComplianceRulesResponse(framework="all", rules=list(COMPLIANCE_RULES.values()), total=len(COMPLIANCE_RULES))
