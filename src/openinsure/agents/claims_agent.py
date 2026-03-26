"""Claims processing agent for OpenInsure.

Handles the claims lifecycle from first notice of loss (FNOL) through
coverage verification, initial reserving, triage, and investigation
support.

When Foundry is available the prompt is built by
:func:`build_claims_assessment_prompt` which injects claims precedents
from the knowledge graph.  The local ``process()`` returns minimal
defaults for graceful degradation.
"""

from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent
from openinsure.domain.limits import PLATFORM_LIMITS

logger = structlog.get_logger()


class ClaimsAgent(InsuranceAgent):
    """Claims intake, verification, reserving, and triage agent.

    In production all reasoning is performed by the Foundry-hosted agent
    using the knowledge-enriched prompt from
    ``prompts.build_claims_assessment_prompt``.  The local :meth:`process`
    returns safe minimal defaults so the system does not crash when
    Foundry is unavailable.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="claims_agent",
                agent_version="0.1.0",
                authority_limit=PLATFORM_LIMITS.agents.claims_agent,
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
            AgentCapability(
                name="subrogation_analysis",
                description="Analyze claim for third-party liability and subrogation potential",
                required_inputs=["claim_data"],
                produces=["subrogation_score", "subrogation_basis"],
            ),
        ]

    # ------------------------------------------------------------------
    # Foundry-delegated prompt
    # ------------------------------------------------------------------

    def _build_prompt(self, task: dict[str, Any]) -> str:
        """Build a knowledge-enriched prompt via :func:`build_claims_assessment_prompt`."""
        from openinsure.agents.prompts import build_claims_assessment_prompt

        claim = task.get("claim_report", task)
        policy = task.get("policy")
        return build_claims_assessment_prompt(claim, policy)

    # ------------------------------------------------------------------
    # Local fallback — minimal safe defaults
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return minimal defaults when Foundry is unavailable."""
        task_type = task.get("type", "fnol")
        if task_type == "investigation":
            return {
                "claim_id": task.get("claim_id"),
                "recommended_actions": [],
                "confidence": 0.0,
                "ai_mode": "local_fallback",
                "ai_warning": "AI unavailable — manual investigation required",
            }
        return {
            "fnol": {
                "claim_number": "CLM-PENDING",
                "status": "fnol",
                "cause_of_loss": task.get("claim_report", {}).get("cause_of_loss", "unknown"),
            },
            "coverage_result": {
                "is_covered": False,
                "issues": ["AI unavailable — manual coverage verification required"],
            },
            "reserves": {
                "severity_tier": "unknown",
                "indemnity_reserve": "0",
                "expense_reserve": "0",
                "total_reserve": "0",
            },
            "triage_result": {
                "severity_tier": "unknown",
                "fraud_score": 0.0,
                "fraud_indicators_triggered": [],
                "routing": "manual_review",
                "requires_investigation": False,
                "coverage_confirmed": False,
            },
            "confidence": 0.0,
            "ai_mode": "local_fallback",
            "ai_warning": "AI unavailable — manual claims processing required",
        }
