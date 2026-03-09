"""Claims processing agent for OpenInsure.

Handles the claims lifecycle from first notice of loss (FNOL) through
coverage verification, initial reserving, triage, and investigation
support.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Severity scoring baselines (by cause of loss)
# ---------------------------------------------------------------------------

SEVERITY_BASELINES: dict[str, float] = {
    "data_breach": 7.5,
    "ransomware": 8.0,
    "social_engineering": 5.5,
    "system_failure": 4.0,
    "unauthorized_access": 6.5,
    "denial_of_service": 5.0,
    "other": 5.0,
}

RESERVE_BENCHMARKS: dict[str, dict[str, Decimal]] = {
    "simple": {"indemnity": Decimal("25000"), "expense": Decimal("10000")},
    "moderate": {"indemnity": Decimal("100000"), "expense": Decimal("35000")},
    "complex": {"indemnity": Decimal("500000"), "expense": Decimal("150000")},
    "catastrophe": {"indemnity": Decimal("2000000"), "expense": Decimal("500000")},
}

FRAUD_INDICATORS: list[dict[str, Any]] = [
    {"name": "recent_policy_inception", "weight": 0.15, "description": "Policy bound < 90 days ago"},
    {"name": "prior_claims_frequency", "weight": 0.20, "description": "Multiple claims in 12 months"},
    {"name": "late_reporting", "weight": 0.10, "description": "Loss reported > 30 days after occurrence"},
    {"name": "inconsistent_description", "weight": 0.20, "description": "Description inconsistencies detected"},
    {"name": "high_initial_demand", "weight": 0.15, "description": "Initial demand near policy limit"},
    {"name": "litigated_immediately", "weight": 0.20, "description": "Attorney retained before claim filed"},
]


class ClaimsAgent(InsuranceAgent):
    """Claims intake, verification, reserving, and triage agent.

    Pipeline steps executed by :meth:`process`:
    1. **intake_fnol** – structured data extraction from claim report.
    2. **verify_coverage** – active policy, covered loss type, exclusion check.
    3. **set_reserves** – initial reserves based on comparable claims.
    4. **triage_claim** – complexity tier, fraud indicators, routing.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="claims_agent",
                agent_version="0.1.0",
                authority_limit=Decimal("250000"),
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="intake_fnol",
                description="Process a first notice of loss",
                required_inputs=["claim_report"],
                produces=["structured_fnol"],
            ),
            AgentCapability(
                name="verify_coverage",
                description="Verify policy coverage for the reported loss",
                required_inputs=["fnol", "policy"],
                produces=["coverage_result"],
            ),
            AgentCapability(
                name="set_reserves",
                description="Set initial claim reserves",
                required_inputs=["fnol", "coverage_result"],
                produces=["reserves"],
            ),
            AgentCapability(
                name="triage_claim",
                description="Assign complexity tier and route the claim",
                required_inputs=["fnol", "coverage_result", "reserves"],
                produces=["triage_result"],
            ),
            AgentCapability(
                name="support_investigation",
                description="Provide investigation support and document analysis",
                required_inputs=["claim_id"],
                produces=["investigation_support"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = task.get("type", "fnol")
        if task_type == "investigation":
            return await self._support_investigation(task)
        return await self._full_fnol_pipeline(task)

    async def _full_fnol_pipeline(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute the complete FNOL-to-triage pipeline."""
        claim_report = task.get("claim_report", {})
        policy = task.get("policy", {})

        self.logger.info("claims.pipeline.start")

        # Step 1 – FNOL intake
        fnol = self._intake_fnol(claim_report)

        # Step 2 – Coverage verification
        coverage = self._verify_coverage(fnol, policy)

        # Step 3 – Initial reserves
        reserves = self._set_reserves(fnol, coverage)

        # Step 4 – Triage
        triage = self._triage_claim(fnol, coverage, reserves, task)

        confidence = self._compute_confidence(coverage, triage)

        return {
            "fnol": fnol,
            "coverage_result": coverage,
            "reserves": reserves,
            "triage_result": triage,
            "confidence": confidence,
            "reasoning": {
                "steps": [
                    "fnol_intake",
                    "coverage_verification",
                    "reserve_setting",
                    "triage",
                ],
                "severity_tier": triage.get("severity_tier"),
                "coverage_confirmed": coverage.get("is_covered"),
            },
            "data_sources": [
                "claim_report",
                "policy",
                "comparable_claims",
                "fraud_models",
            ],
            "knowledge_queries": [
                "coverage_rules",
                "exclusion_rules",
                "reserve_benchmarks",
                "fraud_indicators",
            ],
        }

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _intake_fnol(self, report: dict[str, Any]) -> dict[str, Any]:
        """Extract structured fields from a raw claim report."""
        claim_number = f"CLM-{uuid4().hex[:8].upper()}"
        now = datetime.now(UTC)

        fnol: dict[str, Any] = {
            "claim_number": claim_number,
            "status": "fnol",
            "reported_at": now.isoformat(),
            "loss_date": report.get("loss_date", str(date.today())),
            "report_date": report.get("report_date", str(date.today())),
            "cause_of_loss": report.get("cause_of_loss", "other"),
            "loss_description": report.get("description", ""),
            "estimated_loss_amount": report.get("estimated_amount"),
            "policy_number": report.get("policy_number"),
            "claimant_name": report.get("claimant_name"),
            "claimant_contact": report.get("claimant_contact"),
        }

        self.logger.info(
            "claims.fnol.created",
            claim_number=claim_number,
            cause=fnol["cause_of_loss"],
        )
        return fnol

    def _verify_coverage(self, fnol: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        """Verify policy is active and loss is covered."""
        issues: list[str] = []

        # Active policy check
        policy_status = policy.get("status", "unknown")
        is_active = policy_status == "active"
        if not is_active:
            issues.append(f"Policy status is '{policy_status}', not active")

        # Coverage period check
        loss_date = fnol.get("loss_date", str(date.today()))
        eff = policy.get("effective_date")
        exp = policy.get("expiration_date")
        within_period = True
        if eff and exp:
            loss_d = date.fromisoformat(str(loss_date))
            if loss_d < date.fromisoformat(str(eff)) or loss_d > date.fromisoformat(str(exp)):
                within_period = False
                issues.append("Loss date outside coverage period")

        # Covered loss type check
        cause = fnol.get("cause_of_loss", "other")
        exclusions = policy.get("exclusions", [])
        excluded = cause in exclusions
        if excluded:
            issues.append(f"Cause '{cause}' is excluded under policy")

        # Policy limit check
        estimated = fnol.get("estimated_loss_amount")
        aggregate = policy.get("aggregate_limit")
        exceeds_limit = False
        if estimated is not None and aggregate is not None:
            if Decimal(str(estimated)) > Decimal(str(aggregate)):
                exceeds_limit = True
                issues.append("Estimated loss exceeds aggregate limit")

        is_covered = is_active and within_period and not excluded

        result = {
            "is_covered": is_covered,
            "is_active": is_active,
            "within_period": within_period,
            "excluded": excluded,
            "exceeds_limit": exceeds_limit,
            "issues": issues,
        }
        self.logger.info("claims.coverage.verified", covered=is_covered)
        return result

    def _set_reserves(self, fnol: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
        """Set initial reserves based on severity and benchmarks."""
        severity_tier = self._assess_severity(fnol)
        benchmarks = RESERVE_BENCHMARKS.get(severity_tier, RESERVE_BENCHMARKS["moderate"])

        estimated = fnol.get("estimated_loss_amount")
        if estimated is not None:
            est = Decimal(str(estimated))
            indemnity = max(benchmarks["indemnity"], est)
        else:
            indemnity = benchmarks["indemnity"]

        expense = benchmarks["expense"]

        now = datetime.now(UTC)
        reserves = {
            "severity_tier": severity_tier,
            "indemnity_reserve": str(indemnity),
            "expense_reserve": str(expense),
            "total_reserve": str(indemnity + expense),
            "set_date": now.isoformat(),
            "set_by": self.config.agent_id,
            "reserve_confidence": 0.75 if estimated else 0.55,
        }
        self.logger.info(
            "claims.reserves.set",
            severity=severity_tier,
            total=reserves["total_reserve"],
        )
        return reserves

    def _triage_claim(
        self,
        fnol: dict[str, Any],
        coverage: dict[str, Any],
        reserves: dict[str, Any],
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Assign complexity tier, fraud score, and route the claim."""
        severity_tier: str = reserves.get("severity_tier", "moderate")
        fraud_score = self._compute_fraud_score(fnol, task)

        # Specialist routing
        routing = "standard_adjuster"
        if severity_tier == "catastrophe":
            routing = "senior_complex_adjuster"
        elif severity_tier == "complex":
            routing = "complex_adjuster"
        elif fraud_score > 0.6:
            routing = "special_investigations_unit"

        triage_result = {
            "severity_tier": severity_tier,
            "fraud_score": fraud_score,
            "fraud_indicators_triggered": self._triggered_indicators(fnol, task),
            "routing": routing,
            "requires_investigation": fraud_score > 0.5 or severity_tier in ("complex", "catastrophe"),
            "coverage_confirmed": coverage.get("is_covered", False),
        }
        self.logger.info(
            "claims.triaged",
            severity=severity_tier,
            fraud_score=fraud_score,
            routing=routing,
        )
        return triage_result

    # ------------------------------------------------------------------
    # Investigation support
    # ------------------------------------------------------------------

    async def _support_investigation(self, task: dict[str, Any]) -> dict[str, Any]:
        """Provide investigation support data for an existing claim."""
        claim_id = task.get("claim_id")
        self.logger.info("claims.investigation.support", claim_id=claim_id)

        return {
            "claim_id": claim_id,
            "recommended_actions": [
                "request_forensic_report",
                "contact_claimant_for_statement",
                "review_prior_claims_history",
                "obtain_third_party_documentation",
            ],
            "confidence": 0.80,
            "reasoning": {"step": "investigation_support"},
            "data_sources": ["claim_history", "policy", "knowledge_graph"],
            "knowledge_queries": ["investigation_protocols"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assess_severity(fnol: dict[str, Any]) -> str:
        """Classify claim severity tier."""
        cause = fnol.get("cause_of_loss", "other")
        base_score = SEVERITY_BASELINES.get(cause, 5.0)

        estimated = fnol.get("estimated_loss_amount")
        if estimated is not None:
            est = float(Decimal(str(estimated)))
            if est > 1_000_000:
                base_score += 2.0
            elif est > 250_000:
                base_score += 1.0

        if base_score >= 8.0:
            return "catastrophe"
        if base_score >= 6.0:
            return "complex"
        if base_score >= 4.0:
            return "moderate"
        return "simple"

    @staticmethod
    def _compute_fraud_score(fnol: dict[str, Any], task: dict[str, Any]) -> float:
        """Heuristic fraud score 0.0 – 1.0."""
        score = 0.0
        policy = task.get("policy", {})

        # Late reporting
        loss_date = fnol.get("loss_date")
        report_date = fnol.get("report_date")
        if loss_date and report_date:
            delta = (date.fromisoformat(str(report_date)) - date.fromisoformat(str(loss_date))).days
            if delta > 30:
                score += 0.10

        # Recent policy inception
        bound_at = policy.get("bound_at")
        if bound_at and loss_date:
            try:
                bound_d = datetime.fromisoformat(str(bound_at)).date()
                loss_d = date.fromisoformat(str(loss_date))
                if (loss_d - bound_d).days < 90:
                    score += 0.15
            except (ValueError, TypeError):
                pass

        # High demand relative to limit
        estimated = fnol.get("estimated_loss_amount")
        aggregate = policy.get("aggregate_limit")
        if estimated is not None and aggregate is not None:
            ratio = float(Decimal(str(estimated)) / Decimal(str(aggregate)))
            if ratio > 0.8:
                score += 0.15

        return round(min(score, 1.0), 4)

    @staticmethod
    def _triggered_indicators(fnol: dict[str, Any], task: dict[str, Any]) -> list[str]:
        """Return names of fraud indicators that fired."""
        triggered: list[str] = []
        policy = task.get("policy", {})

        loss_date = fnol.get("loss_date")
        report_date = fnol.get("report_date")
        if loss_date and report_date:
            delta = (date.fromisoformat(str(report_date)) - date.fromisoformat(str(loss_date))).days
            if delta > 30:
                triggered.append("late_reporting")

        bound_at = policy.get("bound_at")
        if bound_at and loss_date:
            try:
                bound_d = datetime.fromisoformat(str(bound_at)).date()
                loss_d = date.fromisoformat(str(loss_date))
                if (loss_d - bound_d).days < 90:
                    triggered.append("recent_policy_inception")
            except (ValueError, TypeError):
                pass

        estimated = fnol.get("estimated_loss_amount")
        aggregate = policy.get("aggregate_limit")
        if estimated is not None and aggregate is not None:
            if float(Decimal(str(estimated)) / Decimal(str(aggregate))) > 0.8:
                triggered.append("high_initial_demand")

        return triggered

    @staticmethod
    def _compute_confidence(coverage: dict[str, Any], triage: dict[str, Any]) -> float:
        base = 0.85
        if not coverage.get("is_covered"):
            base -= 0.15
        if triage.get("fraud_score", 0) > 0.5:
            base -= 0.10
        if triage.get("severity_tier") == "catastrophe":
            base -= 0.10
        return round(max(0.0, min(1.0, base)), 4)
