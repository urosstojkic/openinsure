"""Product domain entities for OpenInsure.

Represents insurance product definitions including coverage structures,
rating factors, exclusion rules, and filing requirements.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from openinsure.domain.common import DomainEntity, Money


class ProductStatus(StrEnum):
    """Lifecycle status of an insurance product."""

    draft = "draft"
    active = "active"
    filed = "filed"
    suspended = "suspended"
    retired = "retired"


class RatingFactor(BaseModel):
    """A factor used in premium rating calculations."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    factor_name: str
    factor_type: str = Field(..., description="Factor data type: numeric, categorical, boolean")
    weight: Decimal
    description: str


class CoverageDefinition(BaseModel):
    """Definition of an available coverage within a product."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    coverage_code: str
    coverage_name: str
    description: str
    default_limit: Money
    min_limit: Money
    max_limit: Money
    default_deductible: Money
    available_deductibles: list[Money] = Field(default_factory=list)


class ExclusionRule(BaseModel):
    """A rule defining conditions under which coverage is excluded."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    exclusion_code: str
    description: str
    conditions: dict[str, Any] = Field(default_factory=dict)


class FilingRequirement(BaseModel):
    """Regulatory filing requirement for a specific jurisdiction."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    jurisdiction: str
    filing_status: str = Field(
        ...,
        description="Filing status: filed, pending, not_required, exempt",
    )
    filing_reference: str | None = None


class Product(DomainEntity):
    """An insurance product definition.

    Products define the coverage structure, rating methodology,
    exclusions, and regulatory filings for a line of business.
    """

    product_code: str
    product_name: str
    description: str
    line_of_business: str
    status: ProductStatus = ProductStatus.draft
    version: int = Field(ge=1, default=1)

    # Coverage structure
    coverage_definitions: list[CoverageDefinition] = Field(default_factory=list)

    # Rating
    rating_factors: list[RatingFactor] = Field(default_factory=list)

    # Exclusions
    exclusion_rules: list[ExclusionRule] = Field(default_factory=list)

    # Regulatory
    filing_requirements: list[FilingRequirement] = Field(default_factory=list)

    # Premium bounds
    min_premium: Money
    max_premium: Money

    # Territory and effective dates
    territories: list[str] = Field(default_factory=list)
    effective_date: date
    expiration_date: date | None = None
