"""Tests for the Product domain entity."""

from datetime import date
from decimal import Decimal
from typing import Any

from openinsure.domain.product import (
    CoverageDefinition,
    ExclusionRule,
    FilingRequirement,
    Product,
    ProductStatus,
    RatingFactor,
)


def _make_product(**overrides) -> Product:
    """Helper to create a product with sensible defaults."""
    defaults: dict[str, Any] = {
        "product_code": "CYBER-001",
        "product_name": "Cyber Shield",
        "description": "Comprehensive cyber insurance product",
        "line_of_business": "cyber",
        "status": ProductStatus.active,
        "min_premium": Decimal("2500.00"),
        "max_premium": Decimal("500000.00"),
        "effective_date": date(2026, 1, 1),
    }
    defaults.update(overrides)
    return Product(**defaults)


def _make_coverage_definition(**overrides) -> CoverageDefinition:
    """Helper to create a coverage definition."""
    defaults: dict[str, Any] = {
        "coverage_code": "CYB-LIA",
        "coverage_name": "Cyber Liability",
        "description": "Third-party cyber liability coverage",
        "default_limit": Decimal("1000000.00"),
        "min_limit": Decimal("100000.00"),
        "max_limit": Decimal("5000000.00"),
        "default_deductible": Decimal("10000.00"),
    }
    defaults.update(overrides)
    return CoverageDefinition(**defaults)


class TestCreateProduct:
    """Test creating a product."""

    def test_create_product(self):
        product = _make_product()
        assert product.product_code == "CYBER-001"
        assert product.product_name == "Cyber Shield"
        assert product.line_of_business == "cyber"
        assert product.status == ProductStatus.active
        assert product.id is not None

    def test_product_default_version(self):
        product = _make_product()
        assert product.version == 1

    def test_product_with_version(self):
        product = _make_product(version=3)
        assert product.version == 3

    def test_product_with_territories(self):
        product = _make_product(territories=["US", "CA", "UK"])
        assert len(product.territories) == 3

    def test_product_with_expiration(self):
        product = _make_product(expiration_date=date(2027, 12, 31))
        assert product.expiration_date == date(2027, 12, 31)


class TestProductWithCoverages:
    """Test product with coverage definitions."""

    def test_product_with_coverages(self):
        cov = _make_coverage_definition()
        product = _make_product(coverage_definitions=[cov])
        assert len(product.coverage_definitions) == 1
        assert product.coverage_definitions[0].coverage_code == "CYB-LIA"

    def test_product_with_multiple_coverages(self):
        coverages = [
            _make_coverage_definition(coverage_code="CYB-LIA", coverage_name="Cyber Liability"),
            _make_coverage_definition(coverage_code="CYB-BRE", coverage_name="Data Breach"),
            _make_coverage_definition(coverage_code="CYB-BUS", coverage_name="Business Interruption"),
        ]
        product = _make_product(coverage_definitions=coverages)
        assert len(product.coverage_definitions) == 3

    def test_coverage_definition_with_deductibles(self):
        cov = CoverageDefinition(
            coverage_code="CYB-001",
            coverage_name="Cyber Liability",
            description="Third-party liability",
            default_limit=Decimal("1000000.00"),
            min_limit=Decimal("100000.00"),
            max_limit=Decimal("5000000.00"),
            default_deductible=Decimal("10000.00"),
            available_deductibles=[
                Decimal("5000.00"),
                Decimal("10000.00"),
                Decimal("25000.00"),
                Decimal("50000.00"),
            ],
        )
        assert len(cov.available_deductibles) == 4


class TestRatingFactors:
    """Test rating factors."""

    def test_rating_factors(self):
        factor = RatingFactor(
            factor_name="annual_revenue",
            factor_type="numeric",
            weight=Decimal("1.5"),
            description="Annual revenue factor for premium calculation",
        )
        assert factor.factor_name == "annual_revenue"
        assert factor.weight == Decimal("1.5")

    def test_product_with_rating_factors(self):
        factors = [
            RatingFactor(
                factor_name="annual_revenue",
                factor_type="numeric",
                weight=Decimal("1.5"),
                description="Revenue-based rating factor",
            ),
            RatingFactor(
                factor_name="industry_code",
                factor_type="categorical",
                weight=Decimal("1.2"),
                description="Industry-based risk factor",
            ),
            RatingFactor(
                factor_name="has_mfa",
                factor_type="boolean",
                weight=Decimal("0.95"),
                description="MFA discount factor",
            ),
        ]
        product = _make_product(rating_factors=factors)
        assert len(product.rating_factors) == 3
        names = [f.factor_name for f in product.rating_factors]
        assert "annual_revenue" in names
        assert "has_mfa" in names


class TestExclusionRules:
    """Test exclusion rules."""

    def test_exclusion_rules(self):
        exclusion = ExclusionRule(
            exclusion_code="EXC-WAR",
            description="War and terrorism exclusion",
            conditions={"cause_of_loss": ["war", "terrorism"]},
        )
        assert exclusion.exclusion_code == "EXC-WAR"
        assert "war" in exclusion.conditions["cause_of_loss"]

    def test_product_with_exclusions(self):
        exclusions = [
            ExclusionRule(
                exclusion_code="EXC-WAR",
                description="War and terrorism",
                conditions={"cause_of_loss": ["war", "terrorism"]},
            ),
            ExclusionRule(
                exclusion_code="EXC-KNOWN",
                description="Known prior losses",
                conditions={"known_prior": True},
            ),
        ]
        product = _make_product(exclusion_rules=exclusions)
        assert len(product.exclusion_rules) == 2


class TestFilingRequirements:
    """Test filing requirements."""

    def test_filing_requirements(self):
        filing = FilingRequirement(
            jurisdiction="NY",
            filing_status="filed",
            filing_reference="NY-2026-CYB-001",
        )
        assert filing.jurisdiction == "NY"
        assert filing.filing_status == "filed"

    def test_product_with_filings(self):
        filings = [
            FilingRequirement(
                jurisdiction="NY",
                filing_status="filed",
                filing_reference="NY-2026-001",
            ),
            FilingRequirement(
                jurisdiction="CA",
                filing_status="pending",
            ),
            FilingRequirement(
                jurisdiction="TX",
                filing_status="not_required",
            ),
        ]
        product = _make_product(filing_requirements=filings)
        assert len(product.filing_requirements) == 3
        filed = [f for f in product.filing_requirements if f.filing_status == "filed"]
        assert len(filed) == 1


class TestProductSerialization:
    """Test product serialization."""

    def test_product_serialization(self):
        product = _make_product()
        data = product.model_dump()
        assert data["product_code"] == "CYBER-001"
        assert data["status"] == "active"
        assert data["line_of_business"] == "cyber"

    def test_product_roundtrip(self):
        factor = RatingFactor(
            factor_name="revenue",
            factor_type="numeric",
            weight=Decimal("1.3"),
            description="Revenue factor",
        )
        product = _make_product(rating_factors=[factor])
        data = product.model_dump()
        restored = Product(**data)
        assert restored.product_code == product.product_code
        assert restored.id == product.id
        assert len(restored.rating_factors) == 1

    def test_product_status_values(self):
        for status in ProductStatus:
            product = _make_product(status=status)
            data = product.model_dump()
            assert data["status"] == status.value
