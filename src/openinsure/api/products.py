"""Product API endpoints for OpenInsure.

Manages insurance product definitions, rating, and coverage configuration.
All mutations persist to SQL and trigger async knowledge sync (Cosmos → AI Search)
so Foundry agents always have current product definitions.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_product_repository

router = APIRouter()
logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_product_repository()


# ---------------------------------------------------------------------------
# Knowledge sync — fire-and-forget after product mutations
# ---------------------------------------------------------------------------


async def _sync_product_knowledge(product: dict[str, Any], *, removed: bool = False) -> None:
    """Push product changes to Cosmos DB + AI Search for agent retrieval.

    Runs as a background task so the API response is not delayed.
    Failures are logged but never block the product API.
    """
    try:
        from openinsure.services.product_knowledge_sync import ProductKnowledgeSyncService

        svc = ProductKnowledgeSyncService()
        if removed:
            result = await svc.remove_product(str(product["id"]))
            logger.info("product.knowledge_removed", product_id=product["id"], success=result)
        else:
            result = await svc.sync_product(product)
            logger.info("product.knowledge_synced", product_id=product["id"], result=result)
    except Exception:
        logger.warning("product.knowledge_sync_failed", product_id=product.get("id"), exc_info=True)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProductStatus(StrEnum):
    """Product availability status."""

    ACTIVE = "active"
    DRAFT = "draft"
    RETIRED = "retired"
    SUNSET = "sunset"


class ProductLine(StrEnum):
    """Insurance product line."""

    CYBER = "cyber"
    TECH_EO = "tech_eo"
    MPL = "mpl"
    PROFESSIONAL_INDEMNITY = "professional_indemnity"
    DIRECTORS_OFFICERS = "directors_officers"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CoverageDefinition(BaseModel):
    """A single coverage option within a product."""

    name: str
    description: str = ""
    default_limit: float = 0.0
    max_limit: float = 0.0
    default_deductible: float = 0.0
    is_optional: bool = False


class RatingFactorEntry(BaseModel):
    """A single key→multiplier row in a rating factor table."""

    key: str = Field(..., description="Factor value, e.g. 'technology' or '1-5M'")
    multiplier: float = Field(1.0, description="Premium multiplier for this value")
    description: str = ""


class RatingFactorTable(BaseModel):
    """A named table of rating factors (e.g. industry, revenue band)."""

    name: str = Field(..., description="Factor category, e.g. 'industry'")
    description: str = ""
    entries: list[RatingFactorEntry] = Field(default_factory=list)


class AppetiteRule(BaseModel):
    """A configurable underwriting appetite constraint."""

    name: str = ""
    field: str = Field(..., description="Risk field this rule evaluates")
    operator: str = Field("in", description="Operator: in, not_in, gte, lte, between, eq")
    value: Any = Field(..., description="Threshold or list of acceptable values")
    description: str = ""


class AuthorityLimit(BaseModel):
    """Auto-bind authority thresholds for this product."""

    max_auto_bind_premium: float = 0.0
    max_auto_bind_limit: float = 0.0
    requires_senior_review_above: float = 0.0
    requires_cuo_review_above: float = 0.0


class VersionInfo(BaseModel):
    """Metadata about a product version snapshot."""

    version: str
    created_at: str
    created_by: str = "system"
    change_summary: str = ""
    snapshot: dict[str, Any] = Field(default_factory=dict)


class ProductCreate(BaseModel):
    """Payload for creating a new product."""

    name: str = Field(..., min_length=1, max_length=200)
    product_line: ProductLine
    description: str = ""
    version: str = "1.0"
    coverages: list[CoverageDefinition] = Field(default_factory=list)
    rating_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Rating algorithm configuration (base rates, factors, etc.)",
    )
    rating_factor_tables: list[RatingFactorTable] = Field(
        default_factory=list,
        description="Structured rating factor tables (industry, revenue, security, etc.)",
    )
    underwriting_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Underwriting eligibility rules",
    )
    appetite_rules: list[AppetiteRule] = Field(
        default_factory=list,
        description="Configurable appetite rules for triage",
    )
    authority_limits: AuthorityLimit | None = None
    territories: list[str] = Field(default_factory=list)
    effective_date: str | None = None
    expiration_date: str | None = None
    forms: list[str] = Field(default_factory=list, description="Required application forms")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    """Payload for updating a product."""

    name: str | None = None
    description: str | None = None
    status: ProductStatus | None = None
    coverages: list[CoverageDefinition] | None = None
    rating_rules: dict[str, Any] | None = None
    rating_factor_tables: list[RatingFactorTable] | None = None
    underwriting_rules: dict[str, Any] | None = None
    appetite_rules: list[AppetiteRule] | None = None
    authority_limits: AuthorityLimit | None = None
    territories: list[str] | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    forms: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ProductResponse(BaseModel):
    """Public representation of a product."""

    id: str
    name: str
    product_line: ProductLine
    description: str
    version: str
    status: ProductStatus
    coverages: list[CoverageDefinition]
    rating_rules: dict[str, Any]
    rating_factor_tables: list[RatingFactorTable] = Field(default_factory=list)
    underwriting_rules: dict[str, Any]
    appetite_rules: list[AppetiteRule] = Field(default_factory=list)
    authority_limits: AuthorityLimit | None = None
    territories: list[str] = Field(default_factory=list)
    effective_date: str | None = None
    expiration_date: str | None = None
    forms: list[str] = Field(default_factory=list)
    metadata: dict[str, Any]
    version_history: list[VersionInfo] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ProductList(BaseModel):
    """Paginated list of products."""

    items: list[ProductResponse]
    total: int
    skip: int
    limit: int


class RateRequest(BaseModel):
    """Risk data to calculate a rate."""

    risk_data: dict[str, Any] = Field(..., description="Risk characteristics for rating")
    coverages_requested: list[str] = Field(
        default_factory=list,
        description="Specific coverages to rate; empty means all defaults",
    )


class RateResponse(BaseModel):
    """Calculated rate for given risk data."""

    product_id: str
    base_premium: float
    adjustments: list[dict[str, Any]]
    total_premium: float
    currency: str = "USD"
    rated_coverages: list[dict[str, Any]]


class CoverageListResponse(BaseModel):
    """Available coverages for a product."""

    product_id: str
    coverages: list[CoverageDefinition]


class PublishRequest(BaseModel):
    """Optional body for the publish endpoint."""

    change_summary: str = ""


class VersionCreateRequest(BaseModel):
    """Payload for creating a new product version."""

    change_summary: str = ""


class ProductPerformance(BaseModel):
    """Aggregated product performance metrics."""

    product_id: str
    product_name: str
    policies_in_force: int = 0
    total_gwp: float = 0.0
    loss_ratio: float = 0.0
    bind_rate: float = 0.0
    avg_premium: float = 0.0
    submissions_count: int = 0
    bound_count: int = 0
    declined_count: int = 0
    premium_trend: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_product(product_id: str) -> dict[str, Any]:
    product = await _repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_extended_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Back-fill new fields on legacy records that lack them."""
    record.setdefault("rating_factor_tables", [])
    record.setdefault("appetite_rules", [])
    record.setdefault("authority_limits", None)
    record.setdefault("territories", [])
    record.setdefault("effective_date", None)
    record.setdefault("expiration_date", None)
    record.setdefault("forms", [])
    record.setdefault("version_history", [])
    return record


def _snapshot(record: dict[str, Any]) -> dict[str, Any]:
    """Create a serialisable snapshot of the product (excluding history)."""
    snap = {k: v for k, v in record.items() if k != "version_history"}
    return copy.deepcopy(snap)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(body: ProductCreate, background_tasks: BackgroundTasks) -> ProductResponse:
    """Create a new insurance product definition."""
    pid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": pid,
        "name": body.name,
        "product_line": body.product_line,
        "description": body.description,
        "version": body.version,
        "status": ProductStatus.DRAFT,
        "coverages": [c.model_dump() for c in body.coverages],
        "rating_rules": body.rating_rules,
        "rating_factor_tables": [t.model_dump() for t in body.rating_factor_tables],
        "underwriting_rules": body.underwriting_rules,
        "appetite_rules": [r.model_dump() for r in body.appetite_rules],
        "authority_limits": body.authority_limits.model_dump() if body.authority_limits else None,
        "territories": body.territories,
        "effective_date": body.effective_date,
        "expiration_date": body.expiration_date,
        "forms": body.forms,
        "metadata": body.metadata,
        "version_history": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)
    background_tasks.add_task(_sync_product_knowledge, record)
    return ProductResponse(**record)


@router.get("", response_model=ProductList)
async def list_products(
    status: ProductStatus | None = Query(None, description="Filter by product status"),
    product_line: ProductLine | None = Query(None, description="Filter by product line"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ProductList:
    """List products with optional filtering and pagination."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if product_line is not None:
        filters["product_line"] = product_line

    total = await _repo.count(filters)
    page = await _repo.list_all(filters=filters, skip=skip, limit=limit)
    return ProductList(
        items=[ProductResponse(**_ensure_extended_fields(r)) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str) -> ProductResponse:
    """Retrieve a single product by ID."""
    return ProductResponse(**_ensure_extended_fields(await _get_product(product_id)))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, body: ProductUpdate, background_tasks: BackgroundTasks) -> ProductResponse:
    """Update a product definition.  Persists to SQL and syncs to agent knowledge."""
    record = await _get_product(product_id)
    _ensure_extended_fields(record)
    if record["status"] == ProductStatus.RETIRED:
        raise HTTPException(status_code=409, detail="Cannot update a retired product")

    updates = body.model_dump(exclude_unset=True)
    if "coverages" in updates and updates["coverages"] is not None:
        updates["coverages"] = [c.model_dump() for c in body.coverages]  # type: ignore[union-attr]
    if "rating_factor_tables" in updates and updates["rating_factor_tables"] is not None:
        updates["rating_factor_tables"] = [t.model_dump() for t in body.rating_factor_tables]  # type: ignore[union-attr]
    if "appetite_rules" in updates and updates["appetite_rules"] is not None:
        updates["appetite_rules"] = [r.model_dump() for r in body.appetite_rules]  # type: ignore[union-attr]
    if "authority_limits" in updates and updates["authority_limits"] is not None:
        updates["authority_limits"] = body.authority_limits.model_dump() if body.authority_limits else None
    if "metadata" in updates and updates["metadata"] is not None:
        merged_meta = {**record.get("metadata", {}), **updates["metadata"]}
        updates["metadata"] = merged_meta

    updated = await _repo.update(product_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found after update")
    _ensure_extended_fields(updated)
    background_tasks.add_task(_sync_product_knowledge, updated)
    return ProductResponse(**updated)


@router.post("/{product_id}/publish", response_model=ProductResponse)
async def publish_product(
    product_id: str, background_tasks: BackgroundTasks, body: PublishRequest | None = None
) -> ProductResponse:
    """Publish a draft product, making it active and available for quoting.

    Persists status change + version snapshot to SQL, then syncs to agent knowledge
    so Foundry agents immediately see the published product definition.
    """
    record = await _get_product(product_id)
    _ensure_extended_fields(record)
    if record["status"] == ProductStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Product is already active")
    if record["status"] == ProductStatus.RETIRED:
        raise HTTPException(status_code=409, detail="Cannot publish a retired product")

    now = _now()
    summary = body.change_summary if body else ""
    version_entry = {
        "version": record["version"],
        "created_at": now,
        "created_by": "system",
        "change_summary": summary or f"Published version {record['version']}",
        "snapshot": _snapshot(record),
    }

    updates: dict[str, Any] = {
        "status": ProductStatus.ACTIVE,
        "version_history": [*record.get("version_history", []), version_entry],
    }
    updated = await _repo.update(product_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found after publish")
    _ensure_extended_fields(updated)
    background_tasks.add_task(_sync_product_knowledge, updated)
    return ProductResponse(**updated)


@router.post("/{product_id}/versions", response_model=ProductResponse)
async def create_version(
    product_id: str, background_tasks: BackgroundTasks, body: VersionCreateRequest | None = None
) -> ProductResponse:
    """Create a new version of an existing product (bumps minor version).

    Snapshots the current state, bumps version, resets to draft.
    Persists to SQL and syncs to agent knowledge.
    """
    record = await _get_product(product_id)
    _ensure_extended_fields(record)

    summary = body.change_summary if body else ""
    version_entry = {
        "version": record["version"],
        "created_at": _now(),
        "created_by": "system",
        "change_summary": summary or f"Snapshot before version bump from {record['version']}",
        "snapshot": _snapshot(record),
    }

    # Bump version
    try:
        parts = record["version"].split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        new_version = ".".join(parts)
    except (ValueError, IndexError):
        new_version = record["version"] + ".1"

    updates: dict[str, Any] = {
        "version": new_version,
        "status": ProductStatus.DRAFT,
        "version_history": [*record.get("version_history", []), version_entry],
    }
    updated = await _repo.update(product_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found after version bump")
    _ensure_extended_fields(updated)
    background_tasks.add_task(_sync_product_knowledge, updated)
    return ProductResponse(**updated)


@router.get("/{product_id}/performance", response_model=ProductPerformance)
async def get_product_performance(product_id: str) -> ProductPerformance:
    """Return aggregated performance metrics for a product.

    In production this would query the policy/claims data stores. For now
    we return realistic stub data so the UI has something to render.
    """
    record = await _get_product(product_id)
    _ensure_extended_fields(record)

    # Stub performance data — seeded products get realistic numbers
    import hashlib

    seed = int(hashlib.md5(product_id.encode()).hexdigest()[:8], 16)  # noqa: S324
    rng = __import__("random").Random(seed)

    policies = rng.randint(80, 600)
    gwp = round(rng.uniform(2_000_000, 25_000_000), 2)
    submissions = rng.randint(200, 1200)
    bound = rng.randint(int(submissions * 0.3), int(submissions * 0.7))
    declined = submissions - bound - rng.randint(0, int(submissions * 0.1))

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    trend = [{"month": m, "premium": round(rng.uniform(150_000, 600_000), 2)} for m in months]

    return ProductPerformance(
        product_id=product_id,
        product_name=record["name"],
        policies_in_force=policies,
        total_gwp=gwp,
        loss_ratio=round(rng.uniform(0.35, 0.72), 2),
        bind_rate=round(bound / max(submissions, 1), 2),
        avg_premium=round(gwp / max(policies, 1), 2),
        submissions_count=submissions,
        bound_count=bound,
        declined_count=max(declined, 0),
        premium_trend=trend,
    )


@router.post("/{product_id}/rate", response_model=RateResponse)
async def calculate_rate(product_id: str, body: RateRequest) -> RateResponse:
    """Calculate a rate for given risk data.

    Uses rating_factor_tables when available, otherwise falls back to the
    simple base_rate × flat factors approach.
    """
    record = await _get_product(product_id)
    _ensure_extended_fields(record)
    if record["status"] != ProductStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Rating is only available for active products")

    base_rate = record["rating_rules"].get("base_rate", 1000.0)
    adjustments: list[dict[str, Any]] = []

    # Apply structured factor tables if present
    for table in record.get("rating_factor_tables", []):
        factor_name = table["name"]
        risk_val = str(body.risk_data.get(factor_name, "")).lower()
        for entry in table.get("entries", []):
            if entry["key"].lower() == risk_val:
                adjustments.append({"name": factor_name, "factor": entry["multiplier"]})
                base_rate *= entry["multiplier"]
                break

    # Fallback flat factors
    if not adjustments:
        industry_factor = body.risk_data.get("industry_factor", 1.0)
        revenue_factor = body.risk_data.get("revenue_factor", 1.0)
        base_rate *= industry_factor * revenue_factor
        adjustments = [
            {"name": "industry_factor", "factor": industry_factor},
            {"name": "revenue_factor", "factor": revenue_factor},
        ]

    requested = body.coverages_requested or [c["name"] for c in record["coverages"]]
    rated_coverages = [
        {"name": c["name"], "limit": c["default_limit"], "deductible": c["default_deductible"]}
        for c in record["coverages"]
        if c["name"] in requested
    ]

    return RateResponse(
        product_id=product_id,
        base_premium=record["rating_rules"].get("base_rate", 1000.0),
        adjustments=adjustments,
        total_premium=round(base_rate, 2),
        currency="USD",
        rated_coverages=rated_coverages,
    )


@router.get("/{product_id}/coverages", response_model=CoverageListResponse)
async def list_coverages(product_id: str) -> CoverageListResponse:
    """List available coverages for a product."""
    record = await _get_product(product_id)
    return CoverageListResponse(
        product_id=product_id,
        coverages=[CoverageDefinition(**c) for c in record["coverages"]],
    )
