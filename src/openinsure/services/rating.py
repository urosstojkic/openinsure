"""Cyber insurance rating engine.

Implements configurable premium calculation for cyber insurance products.
The rating engine uses a factor-based approach where:
  base_premium = base_rate * revenue_factor
  adjusted_premium = base_premium * product(all_factors)
  final_premium = max(min_premium, min(max_premium, adjusted_premium))

**v106 — Relational factor loading (issue #164)**:
When a ``product_id`` is supplied, :class:`RatingEngine` loads factors
from the ``rating_factor_tables`` SQL table first.  Hardcoded dicts
(``INDUSTRY_RISK_FACTORS``, ``REVENUE_BANDS``) serve as the fallback
when no relational data exists — backward compatibility is preserved.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from pydantic import BaseModel, Field

from openinsure.domain.limits import PLATFORM_LIMITS

logger = structlog.get_logger()


class RatingInput(BaseModel):
    """Input data required for cyber insurance rating."""

    annual_revenue: Decimal = Field(ge=0)
    employee_count: int = Field(ge=1)
    industry_sic_code: str
    security_maturity_score: float = Field(ge=0.0, le=10.0)
    has_mfa: bool = False
    has_endpoint_protection: bool = False
    has_backup_strategy: bool = False
    has_incident_response_plan: bool = False
    prior_incidents: int = Field(ge=0, default=0)
    requested_limit: Decimal = Field(ge=0, default=PLATFORM_LIMITS.premium.default_requested_limit)
    requested_deductible: Decimal = Field(ge=0, default=PLATFORM_LIMITS.premium.default_requested_deductible)


class RatingResult(BaseModel):
    """Result of premium calculation."""

    base_premium: Decimal
    adjusted_premium: Decimal
    final_premium: Decimal
    factors_applied: dict[str, Decimal]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    warnings: list[str] = Field(default_factory=list)


# -- Hardcoded fallback factors (kept for backward compat) -----------------

# Industry risk multipliers by SIC code prefix
INDUSTRY_RISK_FACTORS: dict[str, Decimal] = {
    "73": Decimal("1.0"),  # Computer services (baseline)
    "72": Decimal("0.9"),  # Computer maintenance
    "60": Decimal("1.5"),  # Banking
    "61": Decimal("1.4"),  # Credit institutions
    "62": Decimal("1.3"),  # Security brokers
    "63": Decimal("1.2"),  # Insurance
    "80": Decimal("1.6"),  # Healthcare
    "82": Decimal("0.8"),  # Education
    "91": Decimal("1.1"),  # Government
    "53": Decimal("0.7"),  # General merchandise
    "58": Decimal("0.8"),  # Eating/drinking
}

# Revenue band factors
REVENUE_BANDS: list[tuple[Decimal, Decimal, Decimal]] = [
    (Decimal("0"), Decimal("1000000"), Decimal("0.8")),
    (Decimal("1000000"), Decimal("5000000"), Decimal("1.0")),
    (Decimal("5000000"), Decimal("10000000"), Decimal("1.15")),
    (Decimal("10000000"), Decimal("25000000"), Decimal("1.3")),
    (Decimal("25000000"), Decimal("50000000"), Decimal("1.5")),
]


# ---------------------------------------------------------------------------
# Product-aware rating engine — loads factors from SQL when available
# ---------------------------------------------------------------------------


class RatingEngine:
    """Product-aware rating engine — loads factors from relational DB.

    When ``product_id`` is provided to :meth:`calculate`, the engine
    queries ``rating_factor_tables`` for that product.  When no
    relational data exists, falls back to the hardcoded
    ``INDUSTRY_RISK_FACTORS`` and ``REVENUE_BANDS`` dicts.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, dict[str, Decimal]]] = {}

    async def load_factors_for_product(
        self, product_id: str, *, as_of_date: str | None = None
    ) -> dict[str, dict[str, Decimal]]:
        """Load rating factor tables from relational DB.

        Returns ``{"industry": {"technology": Decimal("0.85"), ...},
        "revenue_band": {"1-5M": Decimal("1.0"), ...}}``.

        When *as_of_date* is provided, loads only factors effective at
        that date (for historical rating / regulatory audit).  The
        as_of_date path bypasses the cache to ensure correct results.

        Falls back to an empty dict when the relational table has no rows.
        """
        cache_key = f"{product_id}:{as_of_date or 'current'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        from openinsure.infrastructure.factory import get_product_relations_repository

        relations = get_product_relations_repository()
        if relations is None:
            return {}

        try:
            if as_of_date:
                flat = await relations.get_rating_factors_as_of(product_id, as_of_date)
            else:
                flat = await relations.get_rating_factors_flat(product_id)
            # Convert float values to Decimal
            result: dict[str, dict[str, Decimal]] = {}
            for cat, entries in flat.items():
                result[cat] = {k: Decimal(str(v)) for k, v in entries.items()}
            self._cache[cache_key] = result
            if result:
                logger.info(
                    "rating.factors_loaded_from_db",
                    product_id=product_id,
                    categories=list(result.keys()),
                    as_of_date=as_of_date,
                )
            return result
        except Exception:
            logger.debug("rating.factor_load_failed", product_id=product_id, exc_info=True)
            return {}

    async def calculate(
        self,
        product_id: str,
        rating_input: RatingInput,
        *,
        as_of_date: str | None = None,
    ) -> RatingResult:
        """Calculate premium using product-specific factors from DB.

        When *as_of_date* is provided, loads factors effective at that
        date for historical rating (regulatory audit support, #181).
        """
        factors_from_db = await self.load_factors_for_product(
            product_id, as_of_date=as_of_date
        )

        engine = CyberRatingEngine()
        if factors_from_db:
            engine.set_db_factors(factors_from_db)

        return engine.calculate_premium(rating_input)


class CyberRatingEngine:
    """Configurable cyber insurance rating engine."""

    def __init__(
        self,
        base_rate_per_thousand: Decimal = PLATFORM_LIMITS.premium.base_rate_per_thousand,
        min_premium: Decimal = PLATFORM_LIMITS.premium.min_premium,
        max_premium: Decimal = PLATFORM_LIMITS.premium.max_premium,
    ):
        self.base_rate = base_rate_per_thousand
        self.min_premium = min_premium
        self.max_premium = max_premium
        # Optional DB-loaded factors (set via set_db_factors)
        self._db_industry_factors: dict[str, Decimal] | None = None
        self._db_revenue_factors: dict[str, Decimal] | None = None

    def set_db_factors(self, factors: dict[str, dict[str, Decimal]]) -> None:
        """Inject relational factors loaded from DB.

        Accepts the dict returned by ``RatingEngine.load_factors_for_product()``.
        Categories named ``industry`` or ``revenue_band`` override the
        corresponding hardcoded dicts.
        """
        if "industry" in factors:
            self._db_industry_factors = factors["industry"]
        if "revenue_band" in factors:
            self._db_revenue_factors = factors["revenue_band"]

    def calculate_premium(self, rating_input: RatingInput) -> RatingResult:
        """Calculate cyber insurance premium based on risk factors."""
        factors: dict[str, Decimal] = {}
        warnings: list[str] = []

        # Base premium from revenue
        base_premium = (rating_input.annual_revenue / Decimal("1000")) * self.base_rate
        factors["base_rate"] = self.base_rate

        # Revenue band factor
        revenue_factor = self._get_revenue_factor(rating_input.annual_revenue)
        factors["revenue_band"] = revenue_factor

        # Industry risk factor
        industry_factor = self._get_industry_factor(rating_input.industry_sic_code)
        factors["industry_risk"] = industry_factor

        # Security maturity factor (higher score = lower premium)
        security_factor = self._get_security_factor(rating_input.security_maturity_score)
        factors["security_maturity"] = security_factor

        # Security controls credit
        controls_factor = self._get_controls_factor(rating_input)
        factors["security_controls"] = controls_factor

        # Prior incidents loading
        incident_factor = self._get_incident_factor(rating_input.prior_incidents)
        factors["prior_incidents"] = incident_factor
        if rating_input.prior_incidents > 2:
            warnings.append("Multiple prior incidents — consider referral to specialist underwriter")

        # Limit factor
        limit_factor = self._get_limit_factor(rating_input.requested_limit)
        factors["limit_adjustment"] = limit_factor

        # Deductible credit
        deductible_factor = self._get_deductible_factor(rating_input.requested_deductible)
        factors["deductible_credit"] = deductible_factor

        # Calculate adjusted premium
        adjustment = Decimal("1.0")
        for factor_value in [
            revenue_factor,
            industry_factor,
            security_factor,
            controls_factor,
            incident_factor,
            limit_factor,
            deductible_factor,
        ]:
            adjustment *= factor_value

        adjusted_premium = (base_premium * adjustment).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Apply min/max bounds
        final_premium = max(self.min_premium, min(self.max_premium, adjusted_premium))
        final_premium = final_premium.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Confidence based on data completeness
        confidence = self._calculate_confidence(rating_input)

        explanation = self._generate_explanation(rating_input, factors, final_premium)

        logger.info(
            "rating.calculated",
            revenue=str(rating_input.annual_revenue),
            final_premium=str(final_premium),
            confidence=confidence,
        )

        return RatingResult(
            base_premium=base_premium.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            adjusted_premium=adjusted_premium,
            final_premium=final_premium,
            factors_applied=factors,
            confidence=confidence,
            explanation=explanation,
            warnings=warnings,
        )

    def _get_revenue_factor(self, revenue: Decimal) -> Decimal:
        # Try DB-loaded revenue factors first
        if self._db_revenue_factors:
            for key, factor in self._db_revenue_factors.items():
                try:
                    if "-" in key:
                        parts = key.split("-")
                        low = Decimal(parts[0].strip().replace("M", "000000").replace("K", "000"))
                        high = Decimal(parts[1].strip().replace("M", "000000").replace("K", "000"))
                        if low <= revenue < high:
                            return Decimal(str(factor))
                except (ValueError, IndexError):
                    continue
            # If DB factors exist but none matched, use default
            return Decimal("1.0")
        # Fallback to hardcoded bands
        for low, high, factor in REVENUE_BANDS:
            if low <= revenue < high:
                return factor
        return Decimal("1.5")  # Above highest band

    def _get_industry_factor(self, sic_code: str) -> Decimal:
        prefix = sic_code[:2] if len(sic_code) >= 2 else sic_code
        # Try DB-loaded industry factors first
        if self._db_industry_factors:
            # Check by SIC prefix and by full code
            for key in [prefix, sic_code, sic_code.lower()]:
                if key in self._db_industry_factors:
                    return Decimal(str(self._db_industry_factors[key]))
            return Decimal("1.0")
        # Fallback to hardcoded dict
        return INDUSTRY_RISK_FACTORS.get(prefix, Decimal("1.0"))

    def _get_security_factor(self, score: float) -> Decimal:
        if score >= 8.0:
            return Decimal("0.7")
        if score >= 6.0:
            return Decimal("0.85")
        if score >= 4.0:
            return Decimal("1.0")
        if score >= 2.0:
            return Decimal("1.3")
        return Decimal("1.6")

    def _get_controls_factor(self, ri: RatingInput) -> Decimal:
        credit = Decimal("1.0")
        if ri.has_mfa:
            credit -= Decimal("0.05")
        if ri.has_endpoint_protection:
            credit -= Decimal("0.05")
        if ri.has_backup_strategy:
            credit -= Decimal("0.05")
        if ri.has_incident_response_plan:
            credit -= Decimal("0.05")
        return max(Decimal("0.8"), credit)

    def _get_incident_factor(self, incidents: int) -> Decimal:
        if incidents == 0:
            return Decimal("1.0")
        if incidents == 1:
            return Decimal("1.25")
        if incidents == 2:
            return Decimal("1.5")
        return Decimal("2.0")

    def _get_limit_factor(self, limit: Decimal) -> Decimal:
        if limit <= Decimal("500000"):
            return Decimal("0.7")
        if limit <= Decimal("1000000"):
            return Decimal("1.0")
        if limit <= Decimal("2000000"):
            return Decimal("1.3")
        if limit <= Decimal("5000000"):
            return Decimal("1.6")
        return Decimal("2.0")

    def _get_deductible_factor(self, deductible: Decimal) -> Decimal:
        if deductible >= Decimal("100000"):
            return Decimal("0.7")
        if deductible >= Decimal("50000"):
            return Decimal("0.8")
        if deductible >= Decimal("25000"):
            return Decimal("0.9")
        if deductible >= Decimal("10000"):
            return Decimal("0.95")
        return Decimal("1.0")

    def _calculate_confidence(self, ri: RatingInput) -> float:
        score = 0.5  # Base confidence
        if ri.annual_revenue > 0:
            score += 0.1
        if ri.industry_sic_code:
            score += 0.1
        if ri.security_maturity_score > 0:
            score += 0.15
        if any([ri.has_mfa, ri.has_endpoint_protection, ri.has_backup_strategy]):
            score += 0.1
        if ri.prior_incidents >= 0:
            score += 0.05
        return min(1.0, score)

    def _generate_explanation(
        self,
        ri: RatingInput,
        factors: dict[str, Any],
        premium: Decimal,
    ) -> str:
        lines = [f"Premium of ${premium:,.2f} calculated for {ri.industry_sic_code} industry"]
        lines.append(f"Revenue: ${ri.annual_revenue:,.0f}, Employees: {ri.employee_count}")
        lines.append(f"Security maturity: {ri.security_maturity_score}/10")
        lines.append("Factors applied: " + ", ".join(f"{k}={v}" for k, v in factors.items()))
        return ". ".join(lines)
