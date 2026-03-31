"""Tests for the commercial property insurance rating engine.

Validates PropertyRatingEngine produces correct premiums using
construction, fire protection, age, occupancy, and sprinkler factors —
completely different factor model from CyberRatingEngine.
"""

from decimal import Decimal

import pytest

from openinsure.services.rating import (
    BUILDING_AGE_FACTORS,
    CONSTRUCTION_TYPE_FACTORS,
    FIRE_PROTECTION_CLASS_FACTORS,
    OCCUPANCY_TYPE_FACTORS,
    PropertyRatingEngine,
    PropertyRatingInput,
    RatingResult,
)


def _make_property_input(**overrides) -> PropertyRatingInput:
    """Helper to create a PropertyRatingInput with sensible defaults."""
    defaults = {
        "building_value": Decimal("5000000"),
        "construction_type": "masonry",
        "year_built": 2010,
        "square_footage": 25000,
        "fire_protection_class": 4,
        "sprinkler_system": True,
        "occupancy_type": "office",
        "distance_to_fire_station_miles": Decimal("3"),
        "roof_type": "standard",
        "prior_property_losses": Decimal("0"),
        "contents_value": Decimal("500000"),
        "business_income_limit": Decimal("250000"),
    }
    defaults.update(overrides)
    return PropertyRatingInput(**defaults)


@pytest.fixture
def engine() -> PropertyRatingEngine:
    return PropertyRatingEngine()


class TestPropertyBasicPremiumCalculation:
    """Test basic property premium calculation."""

    def test_basic_premium_calculation(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert isinstance(result, RatingResult)
        assert result.final_premium > 0
        assert result.base_premium > 0
        assert result.adjusted_premium > 0
        assert len(result.factors_applied) > 0

    def test_premium_is_decimal(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert isinstance(result.final_premium, Decimal)
        assert isinstance(result.base_premium, Decimal)
        assert isinstance(result.adjusted_premium, Decimal)

    def test_premium_has_two_decimal_places(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert result.final_premium == result.final_premium.quantize(Decimal("0.01"))

    def test_base_premium_formula(self, engine: PropertyRatingEngine):
        """Base premium = building_value / 100 * $0.50."""
        ri = _make_property_input(building_value=Decimal("1000000"))
        result = engine.calculate_premium(ri)
        expected_base = Decimal("1000000") / Decimal("100") * Decimal("0.50")
        assert result.base_premium == expected_base.quantize(Decimal("0.01"))


class TestPropertyMinimumPremiumFloor:
    """Test that the minimum premium floor is respected."""

    def test_minimum_premium_floor(self, engine: PropertyRatingEngine):
        ri = _make_property_input(
            building_value=Decimal("100000"),
            construction_type="fire_resistive",
            fire_protection_class=1,
            year_built=2020,
            sprinkler_system=True,
            occupancy_type="office",
        )
        result = engine.calculate_premium(ri)
        assert result.final_premium >= engine.min_premium

    def test_custom_min_premium(self):
        custom = PropertyRatingEngine(min_premium=Decimal("5000"))
        ri = _make_property_input(building_value=Decimal("100000"))
        result = custom.calculate_premium(ri)
        assert result.final_premium >= Decimal("5000")


class TestPropertyMaximumPremiumCap:
    """Test that the maximum premium cap is respected."""

    def test_maximum_premium_cap(self, engine: PropertyRatingEngine):
        ri = _make_property_input(
            building_value=Decimal("50000000"),
            construction_type="frame",
            fire_protection_class=10,
            year_built=1960,
            sprinkler_system=False,
            occupancy_type="restaurant",
        )
        result = engine.calculate_premium(ri)
        assert result.final_premium <= engine.max_premium

    def test_custom_max_premium(self):
        custom = PropertyRatingEngine(max_premium=Decimal("100000"))
        ri = _make_property_input(
            building_value=Decimal("50000000"),
            construction_type="frame",
            sprinkler_system=False,
        )
        result = custom.calculate_premium(ri)
        assert result.final_premium <= Decimal("100000")


class TestConstructionTypeFactors:
    """Test construction type impact on premium."""

    def test_frame_highest_premium(self, engine: PropertyRatingEngine):
        frame = engine.calculate_premium(_make_property_input(construction_type="frame"))
        fire_resistive = engine.calculate_premium(_make_property_input(construction_type="fire_resistive"))
        assert frame.adjusted_premium > fire_resistive.adjusted_premium

    def test_all_construction_factors(self, engine: PropertyRatingEngine):
        for ctype, expected_factor in CONSTRUCTION_TYPE_FACTORS.items():
            result = engine.calculate_premium(_make_property_input(construction_type=ctype))
            assert result.factors_applied["construction_type"] == expected_factor, (
                f"Construction {ctype} expected {expected_factor}, got {result.factors_applied['construction_type']}"
            )

    def test_unknown_construction_uses_default(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(construction_type="unknown_type"))
        assert result.factors_applied["construction_type"] == Decimal("1.0")

    def test_frame_warning(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(construction_type="frame"))
        assert any("frame" in w.lower() for w in result.warnings)


class TestFireProtectionClassFactors:
    """Test fire protection class impact on premium."""

    def test_best_class_cheapest(self, engine: PropertyRatingEngine):
        best = engine.calculate_premium(_make_property_input(fire_protection_class=1))
        worst = engine.calculate_premium(_make_property_input(fire_protection_class=10))
        assert best.adjusted_premium < worst.adjusted_premium

    def test_fire_class_factors(self, engine: PropertyRatingEngine):
        cases = [
            (1, Decimal("0.8")),
            (3, Decimal("0.8")),
            (4, Decimal("1.0")),
            (6, Decimal("1.0")),
            (7, Decimal("1.3")),
            (8, Decimal("1.3")),
            (9, Decimal("2.0")),
            (10, Decimal("2.0")),
        ]
        for fclass, expected in cases:
            result = engine.calculate_premium(_make_property_input(fire_protection_class=fclass))
            assert result.factors_applied["fire_protection_class"] == expected, (
                f"Fire class {fclass} expected {expected}, got {result.factors_applied['fire_protection_class']}"
            )

    def test_poor_protection_warning(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(fire_protection_class=9))
        assert any("fire protection" in w.lower() for w in result.warnings)


class TestBuildingAgeFactors:
    """Test building age impact on premium."""

    def test_new_building_cheaper(self, engine: PropertyRatingEngine):
        new = engine.calculate_premium(_make_property_input(year_built=2020))
        old = engine.calculate_premium(_make_property_input(year_built=1960))
        assert new.adjusted_premium < old.adjusted_premium

    def test_age_factors(self, engine: PropertyRatingEngine):
        # Reference year is 2026
        cases = [
            (2020, Decimal("0.9")),  # 6 years old → 0-10 band
            (2006, Decimal("1.0")),  # 20 years old → 10-30 band
            (1990, Decimal("1.2")),  # 36 years old → 30-50 band
            (1960, Decimal("1.5")),  # 66 years old → 50+ band
        ]
        for year, expected in cases:
            result = engine.calculate_premium(_make_property_input(year_built=year))
            assert result.factors_applied["building_age"] == expected, (
                f"Year {year} expected {expected}, got {result.factors_applied['building_age']}"
            )

    def test_old_building_warning(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(year_built=1970))
        assert any("50 years" in w.lower() for w in result.warnings)


class TestOccupancyTypeFactors:
    """Test occupancy type impact on premium."""

    def test_restaurant_higher_than_office(self, engine: PropertyRatingEngine):
        restaurant = engine.calculate_premium(_make_property_input(occupancy_type="restaurant"))
        office = engine.calculate_premium(_make_property_input(occupancy_type="office"))
        assert restaurant.adjusted_premium > office.adjusted_premium

    def test_all_occupancy_factors(self, engine: PropertyRatingEngine):
        for occ, expected_factor in OCCUPANCY_TYPE_FACTORS.items():
            result = engine.calculate_premium(_make_property_input(occupancy_type=occ))
            assert result.factors_applied["occupancy_type"] == expected_factor, (
                f"Occupancy {occ} expected {expected_factor}, got {result.factors_applied['occupancy_type']}"
            )

    def test_restaurant_warning(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(occupancy_type="restaurant"))
        assert any("restaurant" in w.lower() for w in result.warnings)


class TestSprinklerFactor:
    """Test sprinkler system discount."""

    def test_sprinkler_discount(self, engine: PropertyRatingEngine):
        with_sprinkler = engine.calculate_premium(_make_property_input(sprinkler_system=True))
        without = engine.calculate_premium(_make_property_input(sprinkler_system=False))
        assert with_sprinkler.adjusted_premium < without.adjusted_premium

    def test_sprinkler_yes_factor(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(sprinkler_system=True))
        assert result.factors_applied["sprinkler_system"] == Decimal("0.7")

    def test_sprinkler_no_factor(self, engine: PropertyRatingEngine):
        result = engine.calculate_premium(_make_property_input(sprinkler_system=False))
        assert result.factors_applied["sprinkler_system"] == Decimal("1.0")


class TestPropertyConfidence:
    """Test property rating confidence calculation."""

    def test_confidence_range(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert 0.0 <= result.confidence <= 1.0

    def test_high_confidence_with_full_data(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert result.confidence >= 0.9

    def test_confidence_never_exceeds_one(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert result.confidence <= 1.0


class TestPropertyExplanation:
    """Test explanation generation for property rating."""

    def test_explanation_exists(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert result.explanation is not None
        assert len(result.explanation) > 0

    def test_explanation_contains_occupancy(self, engine: PropertyRatingEngine):
        ri = _make_property_input(occupancy_type="warehouse")
        result = engine.calculate_premium(ri)
        assert "warehouse" in result.explanation

    def test_explanation_contains_building_value(self, engine: PropertyRatingEngine):
        ri = _make_property_input(building_value=Decimal("5000000"))
        result = engine.calculate_premium(ri)
        assert "5,000,000" in result.explanation

    def test_explanation_contains_factors(self, engine: PropertyRatingEngine):
        ri = _make_property_input()
        result = engine.calculate_premium(ri)
        assert "Factors applied" in result.explanation


class TestPropertyPremiumReasonableness:
    """Test that premiums are in realistic ranges for commercial property."""

    def test_5m_building_reasonable_premium(self, engine: PropertyRatingEngine):
        """A $5M masonry office with sprinklers should produce $10K-$50K premium."""
        ri = _make_property_input(
            building_value=Decimal("5000000"),
            construction_type="masonry",
            year_built=2010,
            fire_protection_class=4,
            sprinkler_system=True,
            occupancy_type="office",
        )
        result = engine.calculate_premium(ri)
        assert Decimal("5000") <= result.final_premium <= Decimal("50000"), (
            f"Expected $5K-$50K for a $5M office, got ${result.final_premium}"
        )

    def test_low_risk_building_cheaper(self, engine: PropertyRatingEngine):
        """Best-case: fire_resistive, class 1, new, office, sprinklers."""
        ri = _make_property_input(
            building_value=Decimal("5000000"),
            construction_type="fire_resistive",
            year_built=2020,
            fire_protection_class=1,
            sprinkler_system=True,
            occupancy_type="office",
        )
        result = engine.calculate_premium(ri)
        # 5M/100 * 0.50 = $25K base * 0.7 * 0.8 * 0.9 * 0.8 * 0.7 = ~$5.6K
        assert result.final_premium < Decimal("15000")

    def test_high_risk_building_expensive(self, engine: PropertyRatingEngine):
        """Worst-case: frame, class 10, old, restaurant, no sprinklers."""
        ri = _make_property_input(
            building_value=Decimal("5000000"),
            construction_type="frame",
            year_built=1960,
            fire_protection_class=10,
            sprinkler_system=False,
            occupancy_type="restaurant",
        )
        result = engine.calculate_premium(ri)
        # 5M/100 * 0.50 = $25K base * 1.8 * 2.0 * 1.5 * 1.5 * 1.0 = $202.5K
        assert result.final_premium > Decimal("100000")

    def test_best_case_all_factors(self, engine: PropertyRatingEngine):
        """Verify best-case factors are applied correctly."""
        ri = _make_property_input(
            building_value=Decimal("5000000"),
            construction_type="fire_resistive",
            year_built=2020,
            fire_protection_class=1,
            sprinkler_system=True,
            occupancy_type="office",
        )
        result = engine.calculate_premium(ri)
        assert result.factors_applied["construction_type"] == Decimal("0.7")
        assert result.factors_applied["fire_protection_class"] == Decimal("0.8")
        assert result.factors_applied["building_age"] == Decimal("0.9")
        assert result.factors_applied["occupancy_type"] == Decimal("0.8")
        assert result.factors_applied["sprinkler_system"] == Decimal("0.7")

    def test_worst_case_all_factors(self, engine: PropertyRatingEngine):
        """Verify worst-case factors are applied correctly."""
        ri = _make_property_input(
            building_value=Decimal("5000000"),
            construction_type="frame",
            year_built=1960,
            fire_protection_class=10,
            sprinkler_system=False,
            occupancy_type="restaurant",
        )
        result = engine.calculate_premium(ri)
        assert result.factors_applied["construction_type"] == Decimal("1.8")
        assert result.factors_applied["fire_protection_class"] == Decimal("2.0")
        assert result.factors_applied["building_age"] == Decimal("1.5")
        assert result.factors_applied["occupancy_type"] == Decimal("1.5")
        assert result.factors_applied["sprinkler_system"] == Decimal("1.0")


class TestPropertyDbFactorOverrides:
    """Test that DB-loaded factors override hardcoded defaults."""

    def test_db_construction_factors_override(self):
        engine = PropertyRatingEngine()
        engine.set_db_factors(
            {
                "construction_type": {
                    "masonry": Decimal("0.5"),
                    "frame": Decimal("2.5"),
                }
            }
        )
        result = engine.calculate_premium(_make_property_input(construction_type="masonry"))
        assert result.factors_applied["construction_type"] == Decimal("0.5")

    def test_db_occupancy_factors_override(self):
        engine = PropertyRatingEngine()
        engine.set_db_factors(
            {
                "occupancy_type": {
                    "office": Decimal("0.6"),
                }
            }
        )
        result = engine.calculate_premium(_make_property_input(occupancy_type="office"))
        assert result.factors_applied["occupancy_type"] == Decimal("0.6")

    def test_db_sprinkler_factors_override(self):
        engine = PropertyRatingEngine()
        engine.set_db_factors(
            {
                "sprinkler_system": {
                    "yes": Decimal("0.5"),
                    "no": Decimal("1.2"),
                }
            }
        )
        result = engine.calculate_premium(_make_property_input(sprinkler_system=True))
        assert result.factors_applied["sprinkler_system"] == Decimal("0.5")


class TestPropertyValueInRangeKey:
    """Test the _value_in_range_key helper method."""

    def test_range_key(self):
        assert PropertyRatingEngine._value_in_range_key(5, "1-10") is True
        assert PropertyRatingEngine._value_in_range_key(0, "1-10") is False
        assert PropertyRatingEngine._value_in_range_key(11, "1-10") is False

    def test_plus_key(self):
        assert PropertyRatingEngine._value_in_range_key(50, "50+") is True
        assert PropertyRatingEngine._value_in_range_key(100, "50+") is True
        assert PropertyRatingEngine._value_in_range_key(49, "50+") is False

    def test_exact_key(self):
        assert PropertyRatingEngine._value_in_range_key(5, "5") is True
        assert PropertyRatingEngine._value_in_range_key(6, "5") is False

    def test_invalid_key(self):
        assert PropertyRatingEngine._value_in_range_key(5, "abc") is False
