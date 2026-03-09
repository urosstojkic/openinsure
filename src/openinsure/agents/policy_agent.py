"""Policy lifecycle management agent for OpenInsure.

Manages binding, endorsements, renewals, and cancellations of insurance
policies.  Every lifecycle action produces a full DecisionRecord for
EU AI Act compliance.
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent

logger = structlog.get_logger()


class PolicyAgent(InsuranceAgent):
    """Policy lifecycle agent.

    Supported task types dispatched by :meth:`process`:
    - ``bind`` – validate bind requirements → create policy record →
      trigger document generation.
    - ``endorse`` – validate change → recalculate premium → update policy.
    - ``renew`` – pull updated data → generate renewal terms.
    - ``cancel`` – process cancellation → calculate earned/unearned premium.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="policy_agent",
                agent_version="0.1.0",
                authority_limit=Decimal("5000000"),
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="bind_policy",
                description="Bind a quoted submission into an active policy",
                required_inputs=["quote", "submission"],
                produces=["policy"],
            ),
            AgentCapability(
                name="endorse_policy",
                description="Process an endorsement on an existing policy",
                required_inputs=["policy_id", "endorsement_request"],
                produces=["updated_policy", "premium_change"],
            ),
            AgentCapability(
                name="renew_policy",
                description="Generate renewal terms for an expiring policy",
                required_inputs=["policy_id"],
                produces=["renewal_terms"],
            ),
            AgentCapability(
                name="cancel_policy",
                description="Process a policy cancellation",
                required_inputs=["policy_id", "cancel_reason"],
                produces=["cancellation_result"],
            ),
            AgentCapability(
                name="generate_documents",
                description="Trigger generation of policy documents",
                required_inputs=["policy_id", "document_type"],
                produces=["document_url"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = task.get("type", "bind")
        handler = {
            "bind": self._bind,
            "endorse": self._endorse,
            "renew": self._renew,
            "cancel": self._cancel,
        }.get(task_type)

        if handler is None:
            raise ValueError(f"Unknown policy task type: {task_type}")

        self.logger.info("policy.task.dispatch", task_type=task_type)
        return await handler(task)

    # ------------------------------------------------------------------
    # Bind
    # ------------------------------------------------------------------

    async def _bind(self, task: dict[str, Any]) -> dict[str, Any]:
        """Bind a submission into an active policy."""
        quote = task.get("quote", {})
        submission = task.get("submission", {})
        terms = quote.get("terms", {})

        # Validate bind requirements
        errors = self._validate_bind_requirements(quote, submission)
        if errors:
            return {
                "success": False,
                "errors": errors,
                "confidence": 0.4,
                "reasoning": {"step": "bind_validation", "errors": errors},
                "data_sources": ["quote", "submission"],
            }

        policy_number = f"POL-{uuid4().hex[:8].upper()}"
        now = datetime.now(UTC)
        premium = Decimal(terms.get("annual_premium", "0"))

        policy = {
            "policy_number": policy_number,
            "status": "active",
            "submission_id": submission.get("submission_id"),
            "effective_date": submission.get("requested_effective_date", str(date.today())),
            "expiration_date": submission.get(
                "requested_expiration_date",
                str(date.today().replace(year=date.today().year + 1)),
            ),
            "coverages": [
                {
                    "coverage_code": "CYB-001",
                    "coverage_name": "Cyber Liability",
                    "limit": terms.get("aggregate_limit"),
                    "deductible": terms.get("deductible"),
                    "premium": terms.get("annual_premium"),
                }
            ],
            "total_premium": str(premium),
            "written_premium": str(premium),
            "earned_premium": "0.00",
            "unearned_premium": str(premium),
            "bound_at": now.isoformat(),
            "documents_requested": ["declarations", "policy_form"],
        }

        self.logger.info(
            "policy.bound",
            policy_number=policy_number,
            premium=str(premium),
        )

        return {
            "success": True,
            "policy": policy,
            "confidence": 0.92,
            "reasoning": {
                "step": "bind",
                "premium": str(premium),
                "policy_number": policy_number,
            },
            "data_sources": ["quote", "submission", "product_definitions"],
            "knowledge_queries": ["bind_requirements", "document_templates"],
        }

    @staticmethod
    def _validate_bind_requirements(quote: dict[str, Any], submission: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not quote.get("terms"):
            errors.append("Quote has no terms")
        authority = quote.get("authority", {})
        if authority.get("requires_referral") and not authority.get("referral_approved"):
            errors.append("Quote requires referral approval before binding")
        if not submission.get("line_of_business"):
            errors.append("Submission missing line of business")
        return errors

    # ------------------------------------------------------------------
    # Endorse
    # ------------------------------------------------------------------

    async def _endorse(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process an endorsement on an existing policy."""
        policy = task.get("policy", {})
        request = task.get("endorsement_request", {})
        change_type = request.get("change_type", "unknown")

        current_premium = Decimal(str(policy.get("total_premium", "0")))
        premium_change = self._calculate_endorsement_premium(request, current_premium)
        new_premium = current_premium + premium_change

        endorsement = {
            "endorsement_number": f"END-{uuid4().hex[:6].upper()}",
            "effective_date": request.get("effective_date", str(date.today())),
            "change_type": change_type,
            "description": request.get("description", "Policy endorsement"),
            "premium_change": str(premium_change),
            "new_total_premium": str(new_premium),
            "coverages_modified": request.get("coverages_modified", []),
        }

        self.logger.info(
            "policy.endorsed",
            change_type=change_type,
            premium_change=str(premium_change),
        )

        return {
            "success": True,
            "endorsement": endorsement,
            "updated_premium": str(new_premium),
            "confidence": 0.88,
            "reasoning": {
                "step": "endorse",
                "change_type": change_type,
                "premium_change": str(premium_change),
            },
            "data_sources": ["policy", "endorsement_request", "rating_tables"],
            "knowledge_queries": [
                "endorsement_rules",
                f"premium_adjustment/{change_type}",
            ],
        }

    @staticmethod
    def _calculate_endorsement_premium(request: dict[str, Any], current_premium: Decimal) -> Decimal:
        """Calculate premium change for an endorsement."""
        if "premium_change" in request:
            return Decimal(str(request["premium_change"]))

        change_type = request.get("change_type", "")
        if change_type == "increase_limit":
            return (current_premium * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if change_type == "decrease_limit":
            return -(current_premium * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if change_type == "add_coverage":
            return (current_premium * Decimal("0.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if change_type == "remove_coverage":
            return -(current_premium * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")

    # ------------------------------------------------------------------
    # Renew
    # ------------------------------------------------------------------

    async def _renew(self, task: dict[str, Any]) -> dict[str, Any]:
        """Generate renewal terms for an expiring policy."""
        policy = task.get("policy", {})
        claims_history = task.get("claims_history", [])
        current_premium = Decimal(str(policy.get("total_premium", "0")))

        renewal_factor = self._compute_renewal_factor(claims_history)
        new_premium = (current_premium * renewal_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        today = date.today()
        renewal_terms = {
            "renewal_premium": str(new_premium),
            "renewal_factor": str(renewal_factor),
            "effective_date": str(policy.get("expiration_date", str(today))),
            "expiration_date": str(today.replace(year=today.year + 1)),
            "terms_changed": renewal_factor != Decimal("1.00"),
            "coverages": policy.get("coverages", []),
        }

        self.logger.info(
            "policy.renewal.generated",
            factor=str(renewal_factor),
            new_premium=str(new_premium),
        )

        return {
            "success": True,
            "renewal_terms": renewal_terms,
            "confidence": 0.85,
            "reasoning": {
                "step": "renew",
                "renewal_factor": str(renewal_factor),
                "claims_count": len(claims_history),
            },
            "data_sources": [
                "policy",
                "claims_history",
                "market_rates",
                "loss_experience",
            ],
            "knowledge_queries": [
                "renewal_guidelines",
                "rate_change_limits",
            ],
        }

    @staticmethod
    def _compute_renewal_factor(claims_history: list[dict[str, Any]]) -> Decimal:
        """Compute renewal premium factor based on claims history."""
        if not claims_history:
            return Decimal("0.95")  # Claims-free discount

        total_incurred = sum(Decimal(str(c.get("total_incurred", "0"))) for c in claims_history)
        count = len(claims_history)

        if count >= 3 or total_incurred > Decimal("500000"):
            return Decimal("1.35")
        if count >= 2 or total_incurred > Decimal("100000"):
            return Decimal("1.20")
        if total_incurred > Decimal("25000"):
            return Decimal("1.10")
        return Decimal("1.05")

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def _cancel(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process a policy cancellation."""
        policy = task.get("policy", {})
        reason = task.get("cancel_reason", "insured_request")
        cancel_date = task.get("cancel_date", str(date.today()))

        total_premium = Decimal(str(policy.get("total_premium", "0")))
        earned, unearned = self._calculate_earned_unearned(
            total_premium,
            policy.get("effective_date", str(date.today())),
            policy.get("expiration_date", str(date.today())),
            cancel_date,
        )

        cancellation = {
            "policy_number": policy.get("policy_number"),
            "cancel_date": cancel_date,
            "cancel_reason": reason,
            "total_premium": str(total_premium),
            "earned_premium": str(earned),
            "unearned_premium": str(unearned),
            "return_premium": str(unearned),
            "status": "cancelled",
        }

        self.logger.info(
            "policy.cancelled",
            reason=reason,
            return_premium=str(unearned),
        )

        return {
            "success": True,
            "cancellation": cancellation,
            "confidence": 0.95,
            "reasoning": {
                "step": "cancel",
                "method": "pro_rata",
                "earned": str(earned),
                "unearned": str(unearned),
            },
            "data_sources": ["policy"],
            "knowledge_queries": ["cancellation_rules", "return_premium_methods"],
        }

    @staticmethod
    def _calculate_earned_unearned(
        total_premium: Decimal,
        effective_date: str,
        expiration_date: str,
        cancel_date: str,
    ) -> tuple[Decimal, Decimal]:
        """Pro-rata earned/unearned premium calculation."""
        eff = date.fromisoformat(str(effective_date))
        exp = date.fromisoformat(str(expiration_date))
        cancel = date.fromisoformat(str(cancel_date))

        total_days = max((exp - eff).days, 1)
        elapsed_days = max((cancel - eff).days, 0)
        earned_fraction = Decimal(str(elapsed_days)) / Decimal(str(total_days))

        earned = (total_premium * earned_fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        unearned = total_premium - earned
        return earned, unearned
