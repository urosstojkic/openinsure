"""Unit tests for actuarial service — loss triangles, IBNR, rate adequacy."""

from decimal import Decimal, InvalidOperation

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


# ---------------------------------------------------------------------------
# Adversarial / edge-case tests
# ---------------------------------------------------------------------------

class TestActuarialAdversarial:
    """Tests that try to BREAK the code with malformed, boundary, and hostile inputs."""

    def test_triangle_malformed_numeric_string(self):
        """Non-numeric incurred_amount should raise InvalidOperation or ValueError."""
        claims = [_claim(2020, 12, "not_a_number")]
        with pytest.raises((InvalidOperation, ValueError)):
            generate_loss_triangle("cyber", claims)

    def test_triangle_missing_key(self):
        """Missing 'incurred_amount' key should raise KeyError."""
        claims = [{"accident_year": 2020, "development_month": 12}]
        with pytest.raises(KeyError):
            generate_loss_triangle("cyber", claims)

    def test_triangle_missing_accident_year(self):
        claims = [{"development_month": 12, "incurred_amount": "100"}]
        with pytest.raises(KeyError):
            generate_loss_triangle("cyber", claims)

    def test_triangle_negative_amount(self):
        """Negative amounts should be accepted (represent salvage/recovery)."""
        claims = [_claim(2020, 12, "-500")]
        triangle = generate_loss_triangle("cyber", claims)
        assert triangle[2020][12] == Decimal("-500")

    def test_triangle_none_amount_raises(self):
        """None incurred_amount should raise."""
        claims = [{"accident_year": 2020, "development_month": 12, "incurred_amount": None}]
        with pytest.raises((TypeError, InvalidOperation)):
            generate_loss_triangle("cyber", claims)

    def test_factors_all_zero_denominator(self):
        """All zero current-period values → no factors (division by zero guard)."""
        triangle = {
            2020: {12: Decimal("0"), 24: Decimal("0")},
            2021: {12: Decimal("0"), 24: Decimal("0")},
        }
        factors = _age_to_age_factors(triangle)
        assert 12 not in factors

    def test_ibnr_shrinking_losses(self):
        """Losses that shrink over time → factors < 1 → negative IBNR is possible."""
        triangle = {
            2020: {12: Decimal("1000"), 24: Decimal("500")},
            2021: {12: Decimal("800")},
        }
        result = estimate_ibnr(triangle)
        # Shrinking losses produce negative IBNR (valid actuarially)
        assert "total_ibnr" in result
        total = Decimal(result["total_ibnr"])
        assert isinstance(total, Decimal)

    def test_ibnr_very_large_triangle(self):
        """Large triangle with many years should not crash."""
        triangle = {}
        for year in range(2000, 2025):
            triangle[year] = {}
            for month in range(12, min(12 + (2025 - year) * 12, 300), 12):
                triangle[year][month] = Decimal("10000")
        result = estimate_ibnr(triangle)
        assert "total_ibnr" in result

    def test_rate_adequacy_negative_current_rate(self):
        """Negative current rate → division guard should return 0."""
        current = {"seg": Decimal("-100")}
        indicated = {"seg": Decimal("50")}
        results = calculate_rate_adequacy("cyber", current, indicated)
        # Current rate <= 0, so adequacy should be 0
        assert Decimal(results[0]["adequacy_ratio"]) == Decimal("0")

    def test_rate_adequacy_both_zero(self):
        current = {"seg": Decimal("0")}
        indicated = {"seg": Decimal("0")}
        results = calculate_rate_adequacy("cyber", current, indicated)
        assert Decimal(results[0]["adequacy_ratio"]) == Decimal("0")

    def test_rate_adequacy_very_high_ratio(self):
        """Extreme adequacy ratio (indicated >> current)."""
        current = {"seg": Decimal("1")}
        indicated = {"seg": Decimal("100000")}
        results = calculate_rate_adequacy("cyber", current, indicated)
        ratio = Decimal(results[0]["adequacy_ratio"])
        assert ratio == Decimal("100000.0000")

    def test_triangle_float_precision(self):
        """Float inputs must not lose precision through str conversion."""
        claims = [_claim(2020, 12, 0.1), _claim(2020, 12, 0.2)]
        triangle = generate_loss_triangle("cyber", claims)
        # 0.1 + 0.2 == 0.3 in Decimal (not 0.30000000000000004)
        assert triangle[2020][12] == Decimal("0.1") + Decimal("0.2")
