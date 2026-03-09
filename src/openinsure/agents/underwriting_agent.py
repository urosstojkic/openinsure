"""Underwriting and pricing agent for OpenInsure.

Handles risk assessment, pricing, terms generation, authority checking,
and quote preparation for insurance submissions.  Includes specialised
cyber-risk assessment logic and configurable bind-authority limits.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Rating factors & defaults
# ---------------------------------------------------------------------------

BASE_RATES: dict[str, Decimal] = {
    "cyber": Decimal("0.015"),
    "general_liability": Decimal("0.008"),
    "property": Decimal("0.005"),
}

CYBER_RISK_FACTORS: dict[str, Decimal] = {
    "no_mfa": Decimal("1.25"),
    "no_endpoint_protection": Decimal("1.15"),
    "no_backup": Decimal("1.10"),
    "no_ir_plan": Decimal("1.10"),
    "high_revenue": Decimal("1.20"),
    "prior_incidents_1_2": Decimal("1.15"),
    "prior_incidents_3_plus": Decimal("1.35"),
    "healthcare_sic": Decimal("1.30"),
    "retail_sic": Decimal("1.15"),
}

DEFAULT_LIMITS: dict[str, dict[str, Decimal]] = {
    "cyber": {
        "aggregate_limit": Decimal("5000000"),
        "per_occurrence_limit": Decimal("5000000"),
        "deductible": Decimal("50000"),
    },
    "general_liability": {
        "aggregate_limit": Decimal("2000000"),
        "per_occurrence_limit": Decimal("1000000"),
        "deductible": Decimal("10000"),
    },
    "property": {
        "aggregate_limit": Decimal("10000000"),
        "per_occurrence_limit": Decimal("10000000"),
        "deductible": Decimal("25000"),
    },
}


class UnderwritingAgent(InsuranceAgent):
    """Underwriting, pricing, and quote-generation agent.

    Pipeline steps executed by :meth:`process`:
    1. **assess_risk** – multi-factor risk scoring.
    2. **find_comparables** – retrieve similar bound accounts.
    3. **generate_terms** – limits, deductibles, premium calculation.
    4. **check_authority** – verify auto-bind eligibility.
    5. **prepare_quote** – assemble the quote document payload.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="underwriting_agent",
                agent_version="0.1.0",
                authority_limit=Decimal("1000000"),
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="assess_risk",
                description="Multi-factor risk assessment for a submission",
                required_inputs=["extracted_data", "line_of_business"],
                produces=["risk_assessment"],
            ),
            AgentCapability(
                name="price_submission",
                description="Calculate premium based on risk factors",
                required_inputs=["risk_assessment", "line_of_business"],
                produces=["pricing"],
            ),
            AgentCapability(
                name="generate_terms",
                description="Generate coverage terms (limits, deductibles, premium)",
                required_inputs=["risk_assessment", "pricing"],
                produces=["terms"],
            ),
            AgentCapability(
                name="check_authority",
                description="Check if quote is within auto-bind authority",
                required_inputs=["terms"],
                produces=["authority_result"],
            ),
            AgentCapability(
                name="generate_quote",
                description="Prepare a quote document payload",
                required_inputs=["terms", "authority_result"],
                produces=["quote"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run the full underwriting pipeline.

        Expected *task* keys:
        - ``type``: ``"underwrite"``
        - ``extracted_data``: dict of fields from submission agent
        - ``line_of_business``: str
        - ``triage_result``: optional dict from submission agent
        """
        extracted = task.get("extracted_data", {})
        lob = task.get("line_of_business", "cyber")

        self.logger.info("underwriting.pipeline.start", lob=lob)

        # Step 1 – Risk assessment
        risk = self._assess_risk(extracted, lob)

        # Step 2 – Comparable analysis
        comparables = self._find_comparables(extracted, lob)

        # Step 3 – Terms generation (includes pricing)
        terms = self._generate_terms(risk, extracted, lob)

        # Step 4 – Authority check
        authority = self._check_authority(terms)

        # Step 5 – Quote preparation
        quote = self._prepare_quote(terms, risk, authority)

        confidence = self._compute_confidence(risk, authority)

        return {
            "risk_assessment": risk,
            "comparables": comparables,
            "terms": terms,
            "authority_result": authority,
            "quote": quote,
            "confidence": confidence,
            "reasoning": {
                "risk_factors_applied": risk.get("factors_applied", []),
                "base_rate": str(risk.get("base_rate")),
                "adjusted_rate": str(risk.get("adjusted_rate")),
                "authority_within_limit": authority.get("within_limit"),
            },
            "data_sources": [
                "submission_data",
                "product_rating_tables",
                "comparable_accounts",
                "knowledge_graph",
            ],
            "knowledge_queries": [
                f"rating_factors/{lob}",
                f"authority_limits/{self.config.agent_id}",
                f"comparables/{lob}",
            ],
        }

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _assess_risk(self, extracted: dict[str, Any], lob: str) -> dict[str, Any]:
        """Multi-factor risk assessment."""
        base_rate = BASE_RATES.get(lob, Decimal("0.010"))
        adjusted_rate = base_rate
        factors_applied: list[str] = []

        if lob == "cyber":
            adjusted_rate, factors_applied = self._cyber_risk_assessment(extracted, base_rate)

        overall_score = float(
            min(
                Decimal("10.0"),
                (adjusted_rate / base_rate * Decimal("5.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            )
        )

        return {
            "overall_risk_score": overall_score,
            "base_rate": base_rate,
            "adjusted_rate": adjusted_rate,
            "factors_applied": factors_applied,
            "lob": lob,
        }

    def _cyber_risk_assessment(self, extracted: dict[str, Any], base_rate: Decimal) -> tuple[Decimal, list[str]]:
        """Cyber-specific risk factor adjustments."""
        rate = base_rate
        factors: list[str] = []

        if not extracted.get("has_mfa", True):
            rate *= CYBER_RISK_FACTORS["no_mfa"]
            factors.append("no_mfa")

        if not extracted.get("has_endpoint_protection", True):
            rate *= CYBER_RISK_FACTORS["no_endpoint_protection"]
            factors.append("no_endpoint_protection")

        if not extracted.get("has_backup_strategy", True):
            rate *= CYBER_RISK_FACTORS["no_backup"]
            factors.append("no_backup")

        if not extracted.get("has_incident_response_plan", True):
            rate *= CYBER_RISK_FACTORS["no_ir_plan"]
            factors.append("no_ir_plan")

        prior = int(extracted.get("prior_incidents", 0))
        if prior >= 3:
            rate *= CYBER_RISK_FACTORS["prior_incidents_3_plus"]
            factors.append("prior_incidents_3_plus")
        elif prior >= 1:
            rate *= CYBER_RISK_FACTORS["prior_incidents_1_2"]
            factors.append("prior_incidents_1_2")

        revenue = extracted.get("annual_revenue")
        if revenue is not None and Decimal(str(revenue)) > Decimal("1000000000"):
            rate *= CYBER_RISK_FACTORS["high_revenue"]
            factors.append("high_revenue")

        sic = str(extracted.get("industry_sic_code", ""))
        if sic.startswith("80"):  # Healthcare
            rate *= CYBER_RISK_FACTORS["healthcare_sic"]
            factors.append("healthcare_sic")
        elif sic.startswith(("52", "53")):  # Retail
            rate *= CYBER_RISK_FACTORS["retail_sic"]
            factors.append("retail_sic")

        return (
            rate.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
            factors,
        )

    @staticmethod
    def _find_comparables(extracted: dict[str, Any], lob: str) -> list[dict[str, Any]]:
        """Retrieve comparable bound accounts for benchmarking.

        In production this queries the knowledge graph.  The stub returns
        an empty list so the pipeline remains structurally complete.
        """
        return []

    def _generate_terms(
        self,
        risk: dict[str, Any],
        extracted: dict[str, Any],
        lob: str,
    ) -> dict[str, Any]:
        """Calculate limits, deductibles, and premium."""
        defaults = DEFAULT_LIMITS.get(lob, DEFAULT_LIMITS["cyber"])
        aggregate = defaults["aggregate_limit"]
        per_occ = defaults["per_occurrence_limit"]
        deductible = defaults["deductible"]

        exposure = Decimal(str(extracted.get("annual_revenue", "1000000")))
        adjusted_rate: Decimal = risk["adjusted_rate"]
        premium = (exposure * adjusted_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Enforce product premium bounds
        min_premium = Decimal("5000")
        max_premium = Decimal("25000000")
        premium = max(min_premium, min(premium, max_premium))

        return {
            "aggregate_limit": str(aggregate),
            "per_occurrence_limit": str(per_occ),
            "deductible": str(deductible),
            "annual_premium": str(premium),
            "rate_used": str(adjusted_rate),
            "exposure_base": str(exposure),
        }

    def _check_authority(self, terms: dict[str, Any]) -> dict[str, Any]:
        """Check if the premium is within agent's auto-bind authority."""
        premium = Decimal(terms["annual_premium"])
        within_limit = premium <= self.config.authority_limit

        return {
            "within_limit": within_limit,
            "agent_authority_limit": str(self.config.authority_limit),
            "premium": str(premium),
            "requires_referral": not within_limit,
            "referral_reason": (
                None if within_limit else f"premium {premium} exceeds authority {self.config.authority_limit}"
            ),
        }

    @staticmethod
    def _prepare_quote(
        terms: dict[str, Any],
        risk: dict[str, Any],
        authority: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble the quote document payload."""
        return {
            "terms": terms,
            "risk_summary": {
                "overall_score": risk["overall_risk_score"],
                "factors": risk["factors_applied"],
            },
            "authority": authority,
            "status": "ready" if authority["within_limit"] else "pending_referral",
        }

    @staticmethod
    def _compute_confidence(risk: dict[str, Any], authority: dict[str, Any]) -> float:
        """Compute overall pipeline confidence."""
        base = 0.85
        if risk.get("overall_risk_score", 5.0) > 8.0:
            base -= 0.15
        if not authority.get("within_limit"):
            base -= 0.10
        return round(max(0.0, min(1.0, base)), 4)
