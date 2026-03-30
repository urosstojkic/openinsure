"""Tests for multi-currency, product inheritance, and rating factor versioning.

Covers issues #174, #177, and #181.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from openinsure.domain.product import Product, ProductStatus
from openinsure.domain.submission import Submission, SubmissionChannel
from openinsure.services.rating import CyberRatingEngine, RatingEngine, RatingInput, RatingResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(**overrides: Any) -> Product:
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


def _make_rating_input(**overrides: Any) -> RatingInput:
    defaults = {
        "annual_revenue": Decimal("5000000"),
        "employee_count": 50,
        "industry_sic_code": "7372",
        "security_maturity_score": 5.0,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "has_backup_strategy": False,
        "has_incident_response_plan": False,
        "prior_incidents": 0,
        "requested_limit": Decimal("1000000"),
        "requested_deductible": Decimal("10000"),
    }
    defaults.update(overrides)
    return RatingInput(**defaults)


# ===================================================================
# Issue #174 — Multi-Currency Foundation
# ===================================================================


class TestMultiCurrencyProduct:
    """Test currency field on Product domain entity."""

    def test_default_currency_is_usd(self) -> None:
        product = _make_product()
        assert product.currency == "USD"

    def test_custom_currency(self) -> None:
        product = _make_product(currency="GBP")
        assert product.currency == "GBP"

    def test_eur_currency(self) -> None:
        product = _make_product(currency="EUR")
        assert product.currency == "EUR"

    def test_currency_in_serialization(self) -> None:
        product = _make_product(currency="GBP")
        data = product.model_dump()
        assert data["currency"] == "GBP"

    def test_currency_roundtrip(self) -> None:
        product = _make_product(currency="CAD")
        data = product.model_dump()
        restored = Product(**data)
        assert restored.currency == "CAD"


class TestMultiCurrencySubmission:
    """Test currency field on Submission domain entity."""

    def test_default_currency_is_usd(self) -> None:
        from uuid import uuid4

        sub = Submission(
            submission_number="SUB-001",
            channel=SubmissionChannel.api,
            line_of_business="cyber",
            applicant=uuid4(),
            requested_effective_date=date(2026, 1, 1),
            requested_expiration_date=date(2027, 1, 1),
        )
        assert sub.currency == "USD"

    def test_custom_currency(self) -> None:
        from uuid import uuid4

        sub = Submission(
            submission_number="SUB-002",
            channel=SubmissionChannel.api,
            line_of_business="cyber",
            applicant=uuid4(),
            requested_effective_date=date(2026, 1, 1),
            requested_expiration_date=date(2027, 1, 1),
            currency="GBP",
        )
        assert sub.currency == "GBP"

    def test_currency_in_serialization(self) -> None:
        from uuid import uuid4

        sub = Submission(
            submission_number="SUB-003",
            channel=SubmissionChannel.portal,
            line_of_business="cyber",
            applicant=uuid4(),
            requested_effective_date=date(2026, 1, 1),
            requested_expiration_date=date(2027, 1, 1),
            currency="EUR",
        )
        data = sub.model_dump()
        assert data["currency"] == "EUR"


# ===================================================================
# Issue #177 — Product Template Inheritance
# ===================================================================


class TestProductTemplateFields:
    """Test new template/inheritance fields on Product."""

    def test_default_no_parent(self) -> None:
        product = _make_product()
        assert product.parent_product_id is None
        assert product.is_template is False

    def test_set_parent_product_id(self) -> None:
        from uuid import uuid4

        parent_id = uuid4()
        product = _make_product(parent_product_id=parent_id)
        assert product.parent_product_id == parent_id

    def test_is_template_flag(self) -> None:
        product = _make_product(is_template=True)
        assert product.is_template is True

    def test_template_serialization(self) -> None:
        from uuid import uuid4

        parent_id = uuid4()
        product = _make_product(parent_product_id=parent_id, is_template=True)
        data = product.model_dump()
        assert data["parent_product_id"] == parent_id
        assert data["is_template"] is True

    def test_template_roundtrip(self) -> None:
        from uuid import uuid4

        parent_id = uuid4()
        product = _make_product(parent_product_id=parent_id, is_template=True)
        data = product.model_dump()
        restored = Product(**data)
        assert restored.parent_product_id == parent_id
        assert restored.is_template is True


class TestProductInheritanceMerge:
    """Test the _merge_list_by_key static method from SqlProductRepository."""

    def test_merge_coverages_additive(self) -> None:
        from openinsure.infrastructure.repositories.sql_products import SqlProductRepository

        parent_coverages = [
            {"name": "cyber_liability", "default_limit": 1000000},
            {"name": "data_breach", "default_limit": 500000},
        ]
        child_coverages = [
            {"name": "cyber_liability", "default_limit": 2000000},  # Override
        ]
        result = SqlProductRepository._merge_list_by_key(parent_coverages, child_coverages, key_field="name")
        assert len(result) == 2
        # Child override should be present
        cyber = next(c for c in result if c["name"] == "cyber_liability")
        assert cyber["default_limit"] == 2000000
        # Parent-only coverage should be inherited
        breach = next(c for c in result if c["name"] == "data_breach")
        assert breach["default_limit"] == 500000

    def test_merge_empty_parent(self) -> None:
        from openinsure.infrastructure.repositories.sql_products import SqlProductRepository

        child = [{"name": "a", "val": 1}]
        result = SqlProductRepository._merge_list_by_key([], child, key_field="name")
        assert result == child

    def test_merge_empty_child(self) -> None:
        from openinsure.infrastructure.repositories.sql_products import SqlProductRepository

        parent = [{"name": "a", "val": 1}]
        result = SqlProductRepository._merge_list_by_key(parent, [], key_field="name")
        assert len(result) == 1

    def test_merge_no_overlap(self) -> None:
        from openinsure.infrastructure.repositories.sql_products import SqlProductRepository

        parent = [{"name": "a"}, {"name": "b"}]
        child = [{"name": "c"}, {"name": "d"}]
        result = SqlProductRepository._merge_list_by_key(parent, child, key_field="name")
        assert len(result) == 4

    def test_merge_case_insensitive(self) -> None:
        from openinsure.infrastructure.repositories.sql_products import SqlProductRepository

        parent = [{"name": "Cyber_Liability"}]
        child = [{"name": "cyber_liability"}]
        result = SqlProductRepository._merge_list_by_key(parent, child, key_field="name")
        # Child should override parent (case insensitive match)
        assert len(result) == 1
        assert result[0]["name"] == "cyber_liability"

    def test_merge_rating_factors(self) -> None:
        from openinsure.infrastructure.repositories.sql_products import SqlProductRepository

        parent_factors = [
            {"factor_name": "industry", "weight": 1.0},
            {"factor_name": "revenue", "weight": 1.0},
        ]
        child_factors = [
            {"factor_name": "industry", "weight": 1.5},  # Override
            {"factor_name": "geography", "weight": 0.8},  # New factor
        ]
        result = SqlProductRepository._merge_list_by_key(parent_factors, child_factors, key_field="factor_name")
        assert len(result) == 3
        industry = next(f for f in result if f["factor_name"] == "industry")
        assert industry["weight"] == 1.5  # Child override


# ===================================================================
# Issue #181 — Rating Factor Version History
# ===================================================================


class TestRatedWithSnapshotId:
    """Test rated_with_snapshot_id field on Submission."""

    def test_default_no_snapshot(self) -> None:
        from uuid import uuid4

        sub = Submission(
            submission_number="SUB-010",
            channel=SubmissionChannel.api,
            line_of_business="cyber",
            applicant=uuid4(),
            requested_effective_date=date(2026, 1, 1),
            requested_expiration_date=date(2027, 1, 1),
        )
        assert sub.rated_with_snapshot_id is None

    def test_set_snapshot_id(self) -> None:
        from uuid import uuid4

        snapshot_id = str(uuid4())
        sub = Submission(
            submission_number="SUB-011",
            channel=SubmissionChannel.api,
            line_of_business="cyber",
            applicant=uuid4(),
            requested_effective_date=date(2026, 1, 1),
            requested_expiration_date=date(2027, 1, 1),
            rated_with_snapshot_id=snapshot_id,
        )
        assert sub.rated_with_snapshot_id == snapshot_id

    def test_snapshot_id_in_serialization(self) -> None:
        from uuid import uuid4

        snapshot_id = str(uuid4())
        sub = Submission(
            submission_number="SUB-012",
            channel=SubmissionChannel.api,
            line_of_business="cyber",
            applicant=uuid4(),
            requested_effective_date=date(2026, 1, 1),
            requested_expiration_date=date(2027, 1, 1),
            rated_with_snapshot_id=snapshot_id,
        )
        data = sub.model_dump()
        assert data["rated_with_snapshot_id"] == snapshot_id


class TestRatingEngineWithDbFactors:
    """Test CyberRatingEngine with injected DB factors (simulating as_of)."""

    def test_db_industry_factors_override(self) -> None:
        engine = CyberRatingEngine()
        engine.set_db_factors(
            {
                "industry": {"73": Decimal("0.5")},  # Lower than hardcoded 1.0
            }
        )
        ri = _make_rating_input(industry_sic_code="7300")
        result = engine.calculate_premium(ri)
        assert result.factors_applied["industry_risk"] == Decimal("0.5")

    def test_db_revenue_factors_override(self) -> None:
        engine = CyberRatingEngine()
        engine.set_db_factors(
            {
                "revenue_band": {"0-1M": Decimal("0.6"), "1M-5M": Decimal("0.9")},
            }
        )
        ri = _make_rating_input(annual_revenue=Decimal("500000"))
        result = engine.calculate_premium(ri)
        assert result.factors_applied["revenue_band"] == Decimal("0.6")

    def test_both_factor_categories(self) -> None:
        engine = CyberRatingEngine()
        engine.set_db_factors(
            {
                "industry": {"73": Decimal("1.2")},
                "revenue_band": {"1M-5M": Decimal("1.1")},
            }
        )
        ri = _make_rating_input(
            industry_sic_code="7300",
            annual_revenue=Decimal("3000000"),
        )
        result = engine.calculate_premium(ri)
        assert result.factors_applied["industry_risk"] == Decimal("1.2")
        assert result.factors_applied["revenue_band"] == Decimal("1.1")

    def test_no_db_factors_uses_hardcoded(self) -> None:
        engine = CyberRatingEngine()
        ri = _make_rating_input(industry_sic_code="8010")  # Healthcare
        result = engine.calculate_premium(ri)
        assert result.factors_applied["industry_risk"] == Decimal("1.6")


class TestRatingEngineAsyncCalculate:
    """Test RatingEngine.calculate with as_of_date parameter."""

    @pytest.mark.asyncio
    async def test_calculate_without_as_of(self) -> None:
        engine = RatingEngine()
        ri = _make_rating_input()
        result = await engine.calculate("test-product-id", ri)
        assert isinstance(result, RatingResult)
        assert result.final_premium > 0

    @pytest.mark.asyncio
    async def test_calculate_with_as_of_date(self) -> None:
        engine = RatingEngine()
        ri = _make_rating_input()
        result = await engine.calculate("test-product-id", ri, as_of_date="2026-01-15")
        assert isinstance(result, RatingResult)
        assert result.final_premium > 0

    @pytest.mark.asyncio
    async def test_calculate_signature_accepts_as_of(self) -> None:
        """Verify the as_of_date parameter is accepted without error."""
        engine = RatingEngine()
        ri = _make_rating_input()
        # Both should work without TypeError
        r1 = await engine.calculate("p1", ri)
        r2 = await engine.calculate("p1", ri, as_of_date="2025-06-01")
        assert r1.final_premium > 0
        assert r2.final_premium > 0
