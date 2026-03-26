"""Underwriting and pricing agent for OpenInsure.

Handles risk assessment, pricing, terms generation, authority checking,
and quote preparation for insurance submissions.

When Foundry is available the prompt is built by
:func:`build_underwriting_prompt` which injects pricing guidelines,
dynamic knowledge, comparable accounts, and learning-loop context.
The local ``process()`` returns minimal defaults for graceful degradation.
"""

from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent
from openinsure.domain.limits import PLATFORM_LIMITS

logger = structlog.get_logger()


class UnderwritingAgent(InsuranceAgent):
    """Underwriting, pricing, and quote-generation agent.

    In production all reasoning is performed by the Foundry-hosted agent
    using the knowledge-enriched prompt from
    ``prompts.build_underwriting_prompt``.  The local :meth:`process`
    returns safe minimal defaults so the system does not crash when
    Foundry is unavailable.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="underwriting_agent",
                agent_version="0.1.0",
                authority_limit=PLATFORM_LIMITS.agents.underwriting_agent,
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
    # Foundry-delegated prompt
    # ------------------------------------------------------------------

    def _build_prompt(self, task: dict[str, Any]) -> str:
        """Build a knowledge-enriched prompt via :func:`build_underwriting_prompt`."""
        from openinsure.agents.prompts import build_underwriting_prompt

        submission = task.get("submission", task)
        triage_result = task.get("triage_result")
        return build_underwriting_prompt(submission, triage_result)

    # ------------------------------------------------------------------
    # Local fallback — minimal safe defaults
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return minimal defaults when Foundry is unavailable."""
        return {
            "risk_assessment": {
                "overall_risk_score": 0,
                "factors_applied": [],
            },
            "comparables": [],
            "terms": {
                "aggregate_limit": "0",
                "per_occurrence_limit": "0",
                "deductible": "0",
                "annual_premium": "0",
                "rate_used": "0",
                "exposure_base": "0",
            },
            "authority_result": {
                "within_limit": False,
                "requires_referral": True,
                "referral_reason": "AI unavailable — manual underwriting required",
            },
            "quote": {
                "terms": {},
                "risk_summary": {"overall_score": 0, "factors": []},
                "authority": {"within_limit": False, "requires_referral": True},
                "status": "pending_referral",
            },
            "confidence": 0.0,
            "ai_mode": "local_fallback",
            "ai_warning": "AI unavailable — manual underwriting required",
        }
