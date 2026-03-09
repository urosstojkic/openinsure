"""Tests for the cyber insurance rating engine.

These tests are CRITICAL — the rating engine is the core pricing logic.
"""

from decimal import Decimal

import pytest

from openinsure.services.rating import (
    INDUSTRY_RISK_FACTORS,
    CyberRatingEngine,
    RatingInput,
    RatingResult,
)


def _make_rating_input(**overrides) -> RatingInput:
    """Helper to create a RatingInput with sensible defaults."""
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


@pytest.fixture
def engine() -> CyberRatingEngine:
    return CyberRatingEngine()


class TestBasicPremiumCalculation:
    """Test basic premium calculation."""

    def test_basic_premium_calculation(self, engine: CyberRatingEngine):
        ri = _make_rating_input()
        result = engine.calculate_premium(ri)
        assert isinstance(result, RatingResult)
        assert result.final_premium > 0
        assert result.base_premium > 0
        assert result.adjusted_premium > 0
        assert len(result.factors_applied) > 0

    def test_premium_is_decimal(self, engine: CyberRatingEngine):
        ri = _make_rating_input()
        result = engine.calculate_premium(ri)
        assert isinstance(result.final_premium, Decimal)
        assert isinstance(result.base_premium, Decimal)
        assert isinstance(result.adjusted_premium, Decimal)

    def test_premium_has_two_decimal_places(self, engine: CyberRatingEngine):
        ri = _make_rating_input()
        result = engine.calculate_premium(ri)
        assert result.final_premium == result.final_premium.quantize(Decimal("0.01"))


class TestMinimumPremiumFloor:
    """Test that the minimum premium floor is respected."""

    def test_minimum_premium_floor(self, engine: CyberRatingEngine):
        # Very small revenue should result in min premium
        ri = _make_rating_input(
            annual_revenue=Decimal("10000"),
            security_maturity_score=9.0,
            has_mfa=True,
            has_endpoint_protection=True,
            has_backup_strategy=True,
            has_incident_response_plan=True,
            requested_limit=Decimal("500000"),
            requested_deductible=Decimal("100000"),
        )
        result = engine.calculate_premium(ri)
        assert result.final_premium >= engine.min_premium

    def test_custom_min_premium(self):
        custom_engine = CyberRatingEngine(min_premium=Decimal("5000"))
        ri = _make_rating_input(annual_revenue=Decimal("10000"))
        result = custom_engine.calculate_premium(ri)
        assert result.final_premium >= Decimal("5000")


class TestMaximumPremiumCap:
    """Test that the maximum premium cap is respected."""

    def test_maximum_premium_cap(self, engine: CyberRatingEngine):
        # Very high revenue with worst risk factors
        ri = _make_rating_input(
            annual_revenue=Decimal("100000000"),
            industry_sic_code="8010",  # Healthcare
            security_maturity_score=1.0,
            has_mfa=False,
            has_endpoint_protection=False,
            has_backup_strategy=False,
            has_incident_response_plan=False,
            prior_incidents=5,
            requested_limit=Decimal("10000000"),
            requested_deductible=Decimal("5000"),
        )
        result = engine.calculate_premium(ri)
        assert result.final_premium <= engine.max_premium

    def test_custom_max_premium(self):
        custom_engine = CyberRatingEngine(max_premium=Decimal("100000"))
        ri = _make_rating_input(
            annual_revenue=Decimal("100000000"),
            prior_incidents=5,
            requested_limit=Decimal("10000000"),
        )
        result = custom_engine.calculate_premium(ri)
        assert result.final_premium <= Decimal("100000")


class TestIndustryRiskFactors:
    """Test industry risk factors."""

    def test_industry_risk_factors(self, engine: CyberRatingEngine):
        base_ri = _make_rating_input(industry_sic_code="7372")  # Computer services
        healthcare_ri = _make_rating_input(industry_sic_code="8010")  # Healthcare
        base_result = engine.calculate_premium(base_ri)
        healthcare_result = engine.calculate_premium(healthcare_ri)
        # Healthcare should have higher premium due to 1.6 vs 1.0 factor
        assert healthcare_result.adjusted_premium > base_result.adjusted_premium

    def test_banking_higher_than_education(self, engine: CyberRatingEngine):
        banking = engine.calculate_premium(_make_rating_input(industry_sic_code="6020"))
        education = engine.calculate_premium(_make_rating_input(industry_sic_code="8200"))
        assert banking.adjusted_premium > education.adjusted_premium

    def test_unknown_industry_uses_default(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(industry_sic_code="9999"))
        assert result.factors_applied["industry_risk"] == Decimal("1.0")

    def test_all_known_industry_factors(self, engine: CyberRatingEngine):
        for prefix, expected_factor in INDUSTRY_RISK_FACTORS.items():
            sic = prefix + "00"
            result = engine.calculate_premium(_make_rating_input(industry_sic_code=sic))
            assert result.factors_applied["industry_risk"] == expected_factor


class TestSecurityMaturityDiscount:
    """Test security maturity score impact on premium."""

    def test_security_maturity_discount(self, engine: CyberRatingEngine):
        high_security = engine.calculate_premium(_make_rating_input(security_maturity_score=9.0))
        low_security = engine.calculate_premium(_make_rating_input(security_maturity_score=1.0))
        assert high_security.adjusted_premium < low_security.adjusted_premium

    def test_high_maturity_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(security_maturity_score=8.5))
        assert result.factors_applied["security_maturity"] == Decimal("0.7")

    def test_medium_high_maturity_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(security_maturity_score=7.0))
        assert result.factors_applied["security_maturity"] == Decimal("0.85")

    def test_medium_maturity_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(security_maturity_score=5.0))
        assert result.factors_applied["security_maturity"] == Decimal("1.0")

    def test_low_maturity_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(security_maturity_score=2.5))
        assert result.factors_applied["security_maturity"] == Decimal("1.3")

    def test_very_low_maturity_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(security_maturity_score=0.5))
        assert result.factors_applied["security_maturity"] == Decimal("1.6")


class TestSecurityControlsCredit:
    """Test security controls credit factors."""

    def test_security_controls_credit(self, engine: CyberRatingEngine):
        all_controls = engine.calculate_premium(
            _make_rating_input(
                has_mfa=True,
                has_endpoint_protection=True,
                has_backup_strategy=True,
                has_incident_response_plan=True,
            )
        )
        no_controls = engine.calculate_premium(
            _make_rating_input(
                has_mfa=False,
                has_endpoint_protection=False,
                has_backup_strategy=False,
                has_incident_response_plan=False,
            )
        )
        assert all_controls.adjusted_premium < no_controls.adjusted_premium

    def test_all_controls_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(
            _make_rating_input(
                has_mfa=True,
                has_endpoint_protection=True,
                has_backup_strategy=True,
                has_incident_response_plan=True,
            )
        )
        assert result.factors_applied["security_controls"] == Decimal("0.8")

    def test_no_controls_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(
            _make_rating_input(
                has_mfa=False,
                has_endpoint_protection=False,
                has_backup_strategy=False,
                has_incident_response_plan=False,
            )
        )
        assert result.factors_applied["security_controls"] == Decimal("1.0")

    def test_single_control_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(
            _make_rating_input(
                has_mfa=True,
                has_endpoint_protection=False,
                has_backup_strategy=False,
                has_incident_response_plan=False,
            )
        )
        assert result.factors_applied["security_controls"] == Decimal("0.95")


class TestPriorIncidentsLoading:
    """Test prior incidents loading."""

    def test_prior_incidents_loading(self, engine: CyberRatingEngine):
        clean = engine.calculate_premium(_make_rating_input(prior_incidents=0))
        with_incidents = engine.calculate_premium(_make_rating_input(prior_incidents=3))
        assert with_incidents.adjusted_premium > clean.adjusted_premium

    def test_zero_incidents_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(prior_incidents=0))
        assert result.factors_applied["prior_incidents"] == Decimal("1.0")

    def test_one_incident_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(prior_incidents=1))
        assert result.factors_applied["prior_incidents"] == Decimal("1.25")

    def test_two_incidents_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(prior_incidents=2))
        assert result.factors_applied["prior_incidents"] == Decimal("1.5")

    def test_many_incidents_factor(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(prior_incidents=5))
        assert result.factors_applied["prior_incidents"] == Decimal("2.0")

    def test_many_incidents_warning(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(prior_incidents=3))
        assert any("prior incidents" in w.lower() for w in result.warnings)

    def test_no_warning_for_two_incidents(self, engine: CyberRatingEngine):
        result = engine.calculate_premium(_make_rating_input(prior_incidents=2))
        assert not any("prior incidents" in w.lower() for w in result.warnings)


class TestHighLimitSurcharge:
    """Test high limit surcharge."""

    def test_high_limit_surcharge(self, engine: CyberRatingEngine):
        low_limit = engine.calculate_premium(_make_rating_input(requested_limit=Decimal("500000")))
        high_limit = engine.calculate_premium(_make_rating_input(requested_limit=Decimal("5000000")))
        assert high_limit.adjusted_premium > low_limit.adjusted_premium

    def test_limit_factors(self, engine: CyberRatingEngine):
        cases = [
            (Decimal("250000"), Decimal("0.7")),
            (Decimal("1000000"), Decimal("1.0")),
            (Decimal("2000000"), Decimal("1.3")),
            (Decimal("5000000"), Decimal("1.6")),
            (Decimal("10000000"), Decimal("2.0")),
        ]
        for limit, expected in cases:
            result = engine.calculate_premium(_make_rating_input(requested_limit=limit))
            assert result.factors_applied["limit_adjustment"] == expected, (
                f"Limit {limit} expected factor {expected}, got {result.factors_applied['limit_adjustment']}"
            )


class TestHighDeductibleCredit:
    """Test high deductible credit."""

    def test_high_deductible_credit(self, engine: CyberRatingEngine):
        low_ded = engine.calculate_premium(_make_rating_input(requested_deductible=Decimal("5000")))
        high_ded = engine.calculate_premium(_make_rating_input(requested_deductible=Decimal("100000")))
        assert high_ded.adjusted_premium < low_ded.adjusted_premium

    def test_deductible_factors(self, engine: CyberRatingEngine):
        cases = [
            (Decimal("5000"), Decimal("1.0")),
            (Decimal("10000"), Decimal("0.95")),
            (Decimal("25000"), Decimal("0.9")),
            (Decimal("50000"), Decimal("0.8")),
            (Decimal("100000"), Decimal("0.7")),
        ]
        for deductible, expected in cases:
            result = engine.calculate_premium(_make_rating_input(requested_deductible=deductible))
            assert result.factors_applied["deductible_credit"] == expected, (
                f"Deductible {deductible} expected factor {expected}"
            )


class TestConfidenceCalculation:
    """Test confidence calculation."""

    def test_confidence_calculation(self, engine: CyberRatingEngine):
        ri = _make_rating_input()
        result = engine.calculate_premium(ri)
        assert 0.0 <= result.confidence <= 1.0

    def test_high_confidence_with_full_data(self, engine: CyberRatingEngine):
        ri = _make_rating_input(
            annual_revenue=Decimal("5000000"),
            security_maturity_score=7.0,
            has_mfa=True,
        )
        result = engine.calculate_premium(ri)
        assert result.confidence >= 0.9

    def test_confidence_never_exceeds_one(self, engine: CyberRatingEngine):
        ri = _make_rating_input(
            annual_revenue=Decimal("5000000"),
            security_maturity_score=7.0,
            has_mfa=True,
            has_endpoint_protection=True,
            has_backup_strategy=True,
        )
        result = engine.calculate_premium(ri)
        assert result.confidence <= 1.0


class TestRatingWithAllControls:
    """Test rating with best-case scenario."""

    def test_rating_with_all_controls(self, engine: CyberRatingEngine):
        ri = _make_rating_input(
            annual_revenue=Decimal("5000000"),
            security_maturity_score=9.0,
            has_mfa=True,
            has_endpoint_protection=True,
            has_backup_strategy=True,
            has_incident_response_plan=True,
            prior_incidents=0,
            requested_limit=Decimal("500000"),
            requested_deductible=Decimal("100000"),
        )
        result = engine.calculate_premium(ri)
        # Best case should produce a relatively low premium
        assert result.factors_applied["security_maturity"] == Decimal("0.7")
        assert result.factors_applied["security_controls"] == Decimal("0.8")
        assert result.factors_applied["limit_adjustment"] == Decimal("0.7")
        assert result.factors_applied["deductible_credit"] == Decimal("0.7")


class TestRatingWithNoControls:
    """Test rating with worst-case scenario."""

    def test_rating_with_no_controls(self, engine: CyberRatingEngine):
        ri = _make_rating_input(
            annual_revenue=Decimal("50000000"),
            industry_sic_code="8010",
            security_maturity_score=1.0,
            has_mfa=False,
            has_endpoint_protection=False,
            has_backup_strategy=False,
            has_incident_response_plan=False,
            prior_incidents=5,
            requested_limit=Decimal("10000000"),
            requested_deductible=Decimal("5000"),
        )
        result = engine.calculate_premium(ri)
        # Worst case should hit or approach max premium
        assert result.factors_applied["security_maturity"] == Decimal("1.6")
        assert result.factors_applied["security_controls"] == Decimal("1.0")
        assert result.factors_applied["prior_incidents"] == Decimal("2.0")
        assert result.final_premium == engine.max_premium


class TestVariousRevenueBands:
    """Test various revenue bands."""

    def test_various_revenue_bands(self, engine: CyberRatingEngine):
        cases = [
            (Decimal("500000"), Decimal("0.8")),
            (Decimal("2500000"), Decimal("1.0")),
            (Decimal("7500000"), Decimal("1.15")),
            (Decimal("15000000"), Decimal("1.3")),
            (Decimal("30000000"), Decimal("1.5")),
            (Decimal("100000000"), Decimal("1.5")),  # Above highest band
        ]
        for revenue, expected_factor in cases:
            result = engine.calculate_premium(_make_rating_input(annual_revenue=revenue))
            assert result.factors_applied["revenue_band"] == expected_factor, (
                f"Revenue {revenue} expected factor {expected_factor}, got {result.factors_applied['revenue_band']}"
            )

    def test_revenue_band_boundaries(self, engine: CyberRatingEngine):
        # Boundary at exactly $1M should fall in the $1M-$5M band
        result = engine.calculate_premium(_make_rating_input(annual_revenue=Decimal("1000000")))
        assert result.factors_applied["revenue_band"] == Decimal("1.0")

        # Just below $1M should be in the $0-$1M band
        result = engine.calculate_premium(_make_rating_input(annual_revenue=Decimal("999999")))
        assert result.factors_applied["revenue_band"] == Decimal("0.8")


class TestExplanationGeneration:
    """Test explanation generation."""

    def test_explanation_generation(self, engine: CyberRatingEngine):
        ri = _make_rating_input()
        result = engine.calculate_premium(ri)
        assert result.explanation is not None
        assert len(result.explanation) > 0
        assert "Premium" in result.explanation
        assert "7372" in result.explanation

    def test_explanation_contains_revenue(self, engine: CyberRatingEngine):
        ri = _make_rating_input(annual_revenue=Decimal("5000000"))
        result = engine.calculate_premium(ri)
        assert "5,000,000" in result.explanation

    def test_explanation_contains_factors(self, engine: CyberRatingEngine):
        ri = _make_rating_input()
        result = engine.calculate_premium(ri)
        assert "Factors applied" in result.explanation
