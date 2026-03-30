# mypy: ignore-errors
"""Knowledge graph API endpoints for OpenInsure.

Exposes the insurance knowledge graph (underwriting guidelines,
product definitions, regulatory requirements, claims precedents,
compliance rules, industry profiles, jurisdiction rules) via a
unified REST API.

**Cosmos DB is the source of truth.**  Every read tries Cosmos first;
the rich in-memory store is the graceful-degradation fallback.
Writes go to Cosmos when available and also update the in-memory cache
so the current process reflects changes immediately.
"""

from __future__ import annotations

from datetime import UTC, datetime
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


class IndustryProfileResponse(BaseModel):
    """Industry-specific risk profiles."""

    industry: str
    profiles: list[dict[str, Any]]
    total: int


class JurisdictionRulesResponse(BaseModel):
    """Jurisdiction-specific compliance rules."""

    territory: str
    rules: list[dict[str, Any]]
    total: int


class KnowledgeSyncStatus(BaseModel):
    """Sync status between Cosmos DB and AI Search."""

    cosmos_available: bool
    source: str  # "cosmos" or "in_memory"
    last_checked: str


# ---------------------------------------------------------------------------
# Input validation models (replaces raw dict[str, Any] parameters)
# ---------------------------------------------------------------------------


class GuidelineUpdateBody(BaseModel):
    """Validated body for updating underwriting guidelines."""

    model_config = {"extra": "allow"}

    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=10000)
    lob: str = Field(default="", max_length=100)
    effective_date: str = Field(default="", max_length=30)
    notes: str = Field(default="", max_length=5000)


class PrecedentUpdateBody(BaseModel):
    """Validated body for updating claims precedents."""

    model_config = {"extra": "allow"}

    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=10000)
    claim_type: str = Field(default="", max_length=100)
    outcome: str = Field(default="", max_length=500)
    reasoning: str = Field(default="", max_length=10000)


class ComplianceRuleUpdateBody(BaseModel):
    """Validated body for updating compliance rules."""

    model_config = {"extra": "allow"}

    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=10000)
    framework: str = Field(default="", max_length=100)
    rule_id: str = Field(default="", max_length=100)
    requirements: str = Field(default="", max_length=10000)


# ---------------------------------------------------------------------------
# Static product data (retained for /products endpoint fallback)
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


def _strip_cosmos_meta(doc: dict[str, Any]) -> dict[str, Any]:
    """Remove Cosmos DB internal metadata keys from a document."""
    return {k: v for k, v in doc.items() if k not in _COSMOS_META_KEYS}


def _cosmos_or_none():
    """Return Cosmos store if available, else None."""
    try:
        return get_knowledge_store()
    except Exception:
        _log.warning("knowledge.cosmos_init_failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/sync-status", response_model=KnowledgeSyncStatus)
async def get_sync_status() -> KnowledgeSyncStatus:
    """Check whether Cosmos DB is reachable and report the active data source."""
    store = _cosmos_or_none()
    cosmos_up = False
    if store:
        try:
            store.query_by_type("guideline")
            cosmos_up = True
        except Exception:
            _log.debug("knowledge.cosmos_probe_failed", exc_info=True)
    return KnowledgeSyncStatus(
        cosmos_available=cosmos_up,
        source="cosmos" if cosmos_up else "in_memory",
        last_checked=datetime.now(UTC).isoformat(),
    )


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_endpoint(
    q: str = Query(..., min_length=1, description="Search query text"),
    type: str | None = Query(None, description="Filter by entity type"),
) -> KnowledgeSearchResponse:
    """Search the knowledge base by text, optionally filtered by entity type."""
    try:
        store = _cosmos_or_none()
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
        store = _cosmos_or_none()
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
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_rating_factors(lob)
            if docs:
                return RatingFactorsResponse(lob=lob, rating_factors=docs[0])
    except Exception:
        _log.warning("knowledge.cosmos_unavailable lob=%s", lob, exc_info=True)

    mem = _mem_store()
    rf = mem.get_rating_factors(lob)
    if rf is None:
        raise HTTPException(status_code=404, detail=f"No rating factors found for LOB: {lob}")
    return RatingFactorsResponse(lob=lob, rating_factors=rf)


@router.get("/coverage-options/{lob}", response_model=CoverageOptionsResponse)
async def get_coverage_options(lob: str) -> CoverageOptionsResponse:
    """Retrieve available coverage options for a line of business."""
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_coverage_options(lob)
            if docs:
                return CoverageOptionsResponse(lob=lob, coverage_options=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable lob=%s", lob, exc_info=True)

    mem = _mem_store()
    opts = mem.get_coverage_options(lob)
    if opts is None:
        raise HTTPException(status_code=404, detail=f"No coverage options found for LOB: {lob}")
    return CoverageOptionsResponse(lob=lob, coverage_options=opts, total=len(opts))


@router.put("/guidelines/{lob}", response_model=GuidelineResponse)
async def update_guidelines(lob: str, body: GuidelineUpdateBody) -> GuidelineResponse:
    """Update underwriting guidelines for a line of business (Product Manager role).

    Writes to Cosmos DB first (source of truth), then updates the in-memory cache.
    """
    body_dict = body.model_dump(exclude_none=True)
    # Always update in-memory for immediate reflection
    mem = _mem_store()
    updated = mem.update_guidelines(lob, body_dict)

    # Persist to Cosmos DB
    try:
        store = _cosmos_or_none()
        if store:
            doc = {
                "id": f"guideline-{lob}",
                "entityType": "guideline",
                "lob": lob,
                "content": str(updated),
                **updated,
            }
            store.upsert_document(doc)
            _log.info("knowledge.guidelines_written_to_cosmos", lob=lob)
    except Exception:
        _log.warning("knowledge.cosmos_write_failed", lob=lob, exc_info=True)

    _log.info("knowledge.guidelines_updated", lob=lob)
    return GuidelineResponse(lob=lob, guidelines=[updated], total=1)


@router.get("/products", response_model=KnowledgeProductResponse)
async def list_knowledge_products(
    lob: str | None = Query(None, description="Filter by line of business"),
) -> KnowledgeProductResponse:
    """List product definitions from the knowledge graph."""
    try:
        store = _cosmos_or_none()
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
        store = _cosmos_or_none()
        if store:
            docs = store.query_claims_precedents(claim_type)
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
        store = _cosmos_or_none()
        if store:
            docs = store.query_claims_precedents()
            if docs:
                return ClaimsPrecedentResponse(claim_type="all", precedents=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=claims_precedents", exc_info=True)

    mem = _mem_store()
    all_prec = mem.list_claims_precedents()
    return ClaimsPrecedentResponse(claim_type="all", precedents=list(all_prec.values()), total=len(all_prec))


@router.put("/claims-precedents/{claim_type}", response_model=ClaimsPrecedentResponse)
async def update_claims_precedent(claim_type: str, body: PrecedentUpdateBody) -> ClaimsPrecedentResponse:
    """Update claims precedents for a claim type. Writes to Cosmos DB."""
    body_dict = body.model_dump(exclude_none=True)
    try:
        store = _cosmos_or_none()
        if store:
            doc = {
                "id": f"claims-precedent-{claim_type}",
                "entityType": "claims_precedent",
                "claim_type": claim_type,
                "content": str(body_dict),
                **body_dict,
            }
            store.upsert_document(doc)
            _log.info("knowledge.claims_precedent_written_to_cosmos", claim_type=claim_type)
            return ClaimsPrecedentResponse(claim_type=claim_type, precedents=[doc], total=1)
    except Exception:
        _log.warning("knowledge.cosmos_write_failed", resource="claims_precedent", exc_info=True)

    return ClaimsPrecedentResponse(claim_type=claim_type, precedents=[body_dict], total=1)


@router.get("/compliance-rules/{framework}", response_model=ComplianceRulesResponse)
async def get_compliance_rules(framework: str) -> ComplianceRulesResponse:
    """Retrieve compliance framework rules."""
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_compliance_rules(framework)
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
        store = _cosmos_or_none()
        if store:
            docs = store.query_compliance_rules()
            if docs:
                return ComplianceRulesResponse(framework="all", rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=compliance_rules", exc_info=True)

    mem = _mem_store()
    all_rules = mem.list_compliance_rules()
    return ComplianceRulesResponse(framework="all", rules=list(all_rules.values()), total=len(all_rules))


@router.put("/compliance-rules/{framework}", response_model=ComplianceRulesResponse)
async def update_compliance_rule(framework: str, body: ComplianceRuleUpdateBody) -> ComplianceRulesResponse:
    """Update compliance rules for a framework. Writes to Cosmos DB."""
    body_dict = body.model_dump(exclude_none=True)
    try:
        store = _cosmos_or_none()
        if store:
            doc = {
                "id": f"compliance-rule-{framework}",
                "entityType": "compliance_rule",
                "framework": framework,
                "content": str(body_dict),
                **body_dict,
            }
            store.upsert_document(doc)
            _log.info("knowledge.compliance_rule_written_to_cosmos", framework=framework)
            return ComplianceRulesResponse(framework=framework, rules=[doc], total=1)
    except Exception:
        _log.warning("knowledge.cosmos_write_failed", resource="compliance_rule", exc_info=True)

    return ComplianceRulesResponse(framework=framework, rules=[body_dict], total=1)


# ---------------------------------------------------------------------------
# Industry profiles & jurisdiction rules — Cosmos-first
# ---------------------------------------------------------------------------


@router.get("/industry-profiles/{industry}", response_model=IndustryProfileResponse)
async def get_industry_profile(industry: str) -> IndustryProfileResponse:
    """Retrieve industry-specific risk profile and regulatory context."""
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_industry_profiles(industry)
            if docs:
                return IndustryProfileResponse(industry=industry, profiles=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=industry_profile", exc_info=True)

    mem = _mem_store()
    profile = mem.get_industry_guidelines(industry)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No profile for industry: {industry}")
    return IndustryProfileResponse(industry=industry, profiles=[profile], total=1)


@router.get("/industry-profiles", response_model=IndustryProfileResponse)
async def list_industry_profiles() -> IndustryProfileResponse:
    """List all industry-specific risk profiles."""
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_industry_profiles()
            if docs:
                return IndustryProfileResponse(industry="all", profiles=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=industry_profiles", exc_info=True)

    mem = _mem_store()
    all_profiles = mem.list_industry_guidelines()
    profiles = [{"industry": k, **v} for k, v in all_profiles.items()]
    return IndustryProfileResponse(industry="all", profiles=profiles, total=len(profiles))


@router.get("/jurisdiction-rules/{territory}", response_model=JurisdictionRulesResponse)
async def get_jurisdiction_rules(territory: str) -> JurisdictionRulesResponse:
    """Retrieve jurisdiction-specific compliance and regulatory rules."""
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_jurisdiction_rules(territory)
            if docs:
                return JurisdictionRulesResponse(territory=territory, rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=jurisdiction_rules", exc_info=True)

    mem = _mem_store()
    rules = mem.get_compliance_rules_for_jurisdiction(territory)
    if rules is None:
        raise HTTPException(status_code=404, detail=f"No rules for territory: {territory}")
    return JurisdictionRulesResponse(territory=territory, rules=[rules], total=1)


@router.get("/jurisdiction-rules", response_model=JurisdictionRulesResponse)
async def list_jurisdiction_rules() -> JurisdictionRulesResponse:
    """List all jurisdiction-specific compliance rules."""
    try:
        store = _cosmos_or_none()
        if store:
            docs = store.query_jurisdiction_rules()
            if docs:
                return JurisdictionRulesResponse(territory="all", rules=docs, total=len(docs))
    except Exception:
        _log.warning("knowledge.cosmos_unavailable resource=jurisdiction_rules", exc_info=True)

    mem = _mem_store()
    all_rules = mem.list_jurisdiction_rules()
    rules = [{"territory": k, **v} for k, v in all_rules.items()]
    return JurisdictionRulesResponse(territory="all", rules=rules, total=len(rules))
