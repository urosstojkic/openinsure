"""Cyber insurance rating engine.

Implements configurable premium calculation for cyber insurance products.
The rating engine uses a factor-based approach where:
  base_premium = base_rate * revenue_factor
  adjusted_premium = base_premium * product(all_factors)
  final_premium = max(min_premium, min(max_premium, adjusted_premium))
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from pydantic import BaseModel, Field

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
    requested_limit: Decimal = Field(ge=0, default=Decimal("1000000"))
    requested_deductible: Decimal = Field(ge=0, default=Decimal("10000"))


class RatingResult(BaseModel):
    """Result of premium calculation."""

    base_premium: Decimal
    adjusted_premium: Decimal
    final_premium: Decimal
    factors_applied: dict[str, Decimal]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    warnings: list[str] = Field(default_factory=list)


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


class CyberRatingEngine:
    """Configurable cyber insurance rating engine."""

    def __init__(
        self,
        base_rate_per_thousand: Decimal = Decimal("1.50"),
        min_premium: Decimal = Decimal("2500"),
        max_premium: Decimal = Decimal("500000"),
    ):
        self.base_rate = base_rate_per_thousand
        self.min_premium = min_premium
        self.max_premium = max_premium

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
        for low, high, factor in REVENUE_BANDS:
            if low <= revenue < high:
                return factor
        return Decimal("1.5")  # Above highest band

    def _get_industry_factor(self, sic_code: str) -> Decimal:
        prefix = sic_code[:2] if len(sic_code) >= 2 else sic_code
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
