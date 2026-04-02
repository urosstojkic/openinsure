"""Unit tests for actuarial service — loss triangles, IBNR, rate adequacy."""

from decimal import Decimal

import pytest

from openinsure.services.actuarial import (
    _age_to_age_factors,
    calculate_rate_adequacy,
    estimate_ibnr,
    generate_loss_triangle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _claim(ay: int, dm: int, amount: str) -> dict:
    return {"accident_year": ay, "development_month": dm, "incurred_amount": amount}


# ---------------------------------------------------------------------------
# generate_loss_triangle
# ---------------------------------------------------------------------------

class TestGenerateLossTriangle:
    def test_basic_triangle(self):
        claims = [
            _claim(2020, 12, "100"),
            _claim(2020, 24, "120"),
            _claim(2021, 12, "200"),
        ]
        triangle = generate_loss_triangle("cyber", claims)
        assert triangle[2020][12] == Decimal("100")
        assert triangle[2020][24] == Decimal("120")
        assert triangle[2021][12] == Decimal("200")

    def test_aggregation_same_cell(self):
        """Multiple claims in the same AY/DM cell should sum."""
        claims = [
            _claim(2020, 12, "100"),
            _claim(2020, 12, "50"),
        ]
        triangle = generate_loss_triangle("cyber", claims)
        assert triangle[2020][12] == Decimal("150")

    def test_empty_claims(self):
        triangle = generate_loss_triangle("property", [])
        assert triangle == {}

    def test_single_claim(self):
        triangle = generate_loss_triangle("cyber", [_claim(2022, 6, "999.99")])
        assert triangle[2022][6] == Decimal("999.99")

    def test_float_string_amount(self):
        """Amounts passed as floats should be safely converted via str."""
        claims = [_claim(2020, 12, 100.5)]
        triangle = generate_loss_triangle("cyber", claims)
        assert triangle[2020][12] == Decimal("100.5")


# ---------------------------------------------------------------------------
# _age_to_age_factors
# ---------------------------------------------------------------------------

class TestAgeToAgeFactors:
    def test_simple_factors(self):
        triangle = {
            2020: {12: Decimal("100"), 24: Decimal("120")},
            2021: {12: Decimal("200"), 24: Decimal("250")},
        }
        factors = _age_to_age_factors(triangle)
        # Weighted average: (120+250) / (100+200) = 370/300 = 1.2333
        assert 12 in factors
        assert factors[12] == Decimal("1.2333")

    def test_single_period(self):
        """A triangle with only one period has no age-to-age factors."""
        triangle = {2020: {12: Decimal("100")}}
        factors = _age_to_age_factors(triangle)
        assert factors == {}

    def test_empty_triangle(self):
        factors = _age_to_age_factors({})
        assert factors == {}

    def test_zero_current_skipped(self):
        """If sum_curr is zero for a period, no factor should be produced."""
        triangle = {
            2020: {12: Decimal("0"), 24: Decimal("100")},
        }
        factors = _age_to_age_factors(triangle)
        assert 12 not in factors


# ---------------------------------------------------------------------------
# estimate_ibnr
# ---------------------------------------------------------------------------

class TestEstimateIBNR:
    def test_chain_ladder_basic(self):
        triangle = {
            2020: {12: Decimal("100"), 24: Decimal("120"), 36: Decimal("130")},
            2021: {12: Decimal("200"), 24: Decimal("240")},
            2022: {12: Decimal("300")},
        }
        result = estimate_ibnr(triangle)
        assert "total_ibnr" in result
        assert "factors" in result
        assert "ultimates" in result
        assert "ibnr_by_year" in result
        # IBNR should be >= 0 overall
        assert Decimal(result["total_ibnr"]) >= 0

    def test_unsupported_method(self):
        with pytest.raises(ValueError, match="Unsupported method"):
            estimate_ibnr({}, method="bornhuetter_ferguson")

    def test_empty_triangle(self):
        result = estimate_ibnr({})
        assert result["total_ibnr"] == "0"
        assert result["factors"] == {}

    def test_single_point_triangle(self):
        """A triangle with one year and one period should produce 0 IBNR."""
        triangle = {2020: {12: Decimal("100")}}
        result = estimate_ibnr(triangle)
        assert result["total_ibnr"] == "0"

    def test_ibnr_values_are_strings(self):
        """All return values should be string-serialized."""
        triangle = {
            2020: {12: Decimal("100"), 24: Decimal("120")},
            2021: {12: Decimal("200")},
        }
        result = estimate_ibnr(triangle)
        for key in ("total_ibnr",):
            assert isinstance(result[key], str)
        for v in result["ultimates"].values():
            assert isinstance(v, str)


# ---------------------------------------------------------------------------
# calculate_rate_adequacy
# ---------------------------------------------------------------------------

class TestCalculateRateAdequacy:
    def test_basic_adequacy(self):
        current = {"cyber_small": Decimal("100"), "cyber_mid": Decimal("200")}
        indicated = {"cyber_small": Decimal("110"), "cyber_mid": Decimal("180")}
        results = calculate_rate_adequacy("cyber", current, indicated)
        assert len(results) == 2
        for r in results:
            assert r["line_of_business"] == "cyber"
            assert "adequacy_ratio" in r

    def test_segment_uses_current_as_fallback(self):
        """If indicated rate missing for a segment, current is used → ratio=1."""
        current = {"seg_a": Decimal("50")}
        indicated = {}
        results = calculate_rate_adequacy("property", current, indicated)
        assert Decimal(results[0]["adequacy_ratio"]) == Decimal("1.0000")

    def test_zero_current_rate(self):
        """Zero current rate should produce adequacy ratio of 0 (safe division)."""
        current = {"seg_a": Decimal("0")}
        indicated = {"seg_a": Decimal("100")}
        results = calculate_rate_adequacy("cyber", current, indicated)
        assert Decimal(results[0]["adequacy_ratio"]) == Decimal("0")

    def test_empty_rates(self):
        results = calculate_rate_adequacy("cyber", {}, {})
        assert results == []

    def test_output_format(self):
        current = {"seg": Decimal("100")}
        indicated = {"seg": Decimal("120")}
        results = calculate_rate_adequacy("cyber", current, indicated)
        r = results[0]
        assert r["segment"] == "seg"
        assert r["current_rate"] == "100"
        assert r["indicated_rate"] == "120"
