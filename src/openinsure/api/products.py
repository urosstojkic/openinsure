"""Product API endpoints for OpenInsure.

Manages insurance product definitions, rating, and coverage configuration.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
_products: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProductStatus(StrEnum):
    """Product availability status."""

    ACTIVE = "active"
    DRAFT = "draft"
    RETIRED = "retired"


class ProductLine(StrEnum):
    """Insurance product line."""

    CYBER = "cyber"
    TECH_EO = "tech_eo"
    MPL = "mpl"


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
    underwriting_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Underwriting eligibility rules",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    """Payload for updating a product."""

    name: str | None = None
    description: str | None = None
    status: ProductStatus | None = None
    coverages: list[CoverageDefinition] | None = None
    rating_rules: dict[str, Any] | None = None
    underwriting_rules: dict[str, Any] | None = None
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
    underwriting_rules: dict[str, Any]
    metadata: dict[str, Any]
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_product(product_id: str) -> dict[str, Any]:
    product = _products.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(body: ProductCreate) -> ProductResponse:
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
        "underwriting_rules": body.underwriting_rules,
        "metadata": body.metadata,
        "created_at": now,
        "updated_at": now,
    }
    _products[pid] = record
    return ProductResponse(**record)


@router.get("", response_model=ProductList)
async def list_products(
    status: ProductStatus | None = Query(None, description="Filter by product status"),
    product_line: ProductLine | None = Query(None, description="Filter by product line"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ProductList:
    """List products with optional filtering and pagination."""
    results = list(_products.values())

    if status is not None:
        results = [p for p in results if p["status"] == status]
    if product_line is not None:
        results = [p for p in results if p["product_line"] == product_line]

    total = len(results)
    page = results[skip : skip + limit]
    return ProductList(
        items=[ProductResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str) -> ProductResponse:
    """Retrieve a single product by ID."""
    return ProductResponse(**_get_product(product_id))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, body: ProductUpdate) -> ProductResponse:
    """Update a product definition."""
    record = _get_product(product_id)
    if record["status"] == ProductStatus.RETIRED:
        raise HTTPException(status_code=409, detail="Cannot update a retired product")

    updates = body.model_dump(exclude_unset=True)
    if "coverages" in updates and updates["coverages"] is not None:
        record["coverages"] = [c.model_dump() for c in body.coverages]  # type: ignore[union-attr]
        del updates["coverages"]
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    return ProductResponse(**record)


@router.post("/{product_id}/rate", response_model=RateResponse)
async def calculate_rate(product_id: str, body: RateRequest) -> RateResponse:
    """Calculate a rate for given risk data.

    Stub implementation — returns a deterministic rate based on product
    base rates.  The real version calls the rating engine.
    """
    record = _get_product(product_id)
    if record["status"] != ProductStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Rating is only available for active products")

    base_rate = record["rating_rules"].get("base_rate", 1000.0)
    industry_factor = body.risk_data.get("industry_factor", 1.0)
    revenue_factor = body.risk_data.get("revenue_factor", 1.0)

    adjusted = base_rate * industry_factor * revenue_factor
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
        base_premium=base_rate,
        adjustments=adjustments,
        total_premium=round(adjusted, 2),
        currency="USD",
        rated_coverages=rated_coverages,
    )


@router.get("/{product_id}/coverages", response_model=CoverageListResponse)
async def list_coverages(product_id: str) -> CoverageListResponse:
    """List available coverages for a product."""
    record = _get_product(product_id)
    return CoverageListResponse(
        product_id=product_id,
        coverages=[CoverageDefinition(**c) for c in record["coverages"]],
    )
