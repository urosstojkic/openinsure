"""Submission intake and triage agent for OpenInsure.

Handles the first stage of the insurance pipeline: receiving submissions,
classifying attached documents, extracting structured data, validating
completeness against product requirements, and triaging the submission
(appetite matching, risk scoring, priority assignment).

When Foundry is available the prompt is built by :func:`build_triage_prompt`
which injects underwriting guidelines, dynamic knowledge, comparable
accounts, and learning-loop context.  The local ``process()`` returns
minimal safe defaults for graceful degradation.
"""

from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent
from openinsure.domain.limits import PLATFORM_LIMITS

logger = structlog.get_logger()


class SubmissionAgent(InsuranceAgent):
    """Submission intake, classification, extraction, and triage agent.

    In production all reasoning is performed by the Foundry-hosted agent
    using the knowledge-enriched prompt from ``prompts.build_triage_prompt``.
    The local :meth:`process` returns safe minimal defaults so the system
    does not crash when Foundry is unavailable.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="submission_agent",
                agent_version="0.1.0",
                authority_limit=PLATFORM_LIMITS.agents.submission_agent,
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="intake",
                description="Receive and register a new insurance submission",
                required_inputs=["submission"],
                produces=["submission_id", "status"],
            ),
            AgentCapability(
                name="classify_documents",
                description="Classify attached documents by type",
                required_inputs=["documents"],
                produces=["classified_documents"],
            ),
            AgentCapability(
                name="extract_data",
                description="Extract structured data from submission documents",
                required_inputs=["classified_documents"],
                produces=["extracted_data"],
            ),
            AgentCapability(
                name="validate_completeness",
                description="Validate extracted data against product requirements",
                required_inputs=["extracted_data", "line_of_business"],
                produces=["validation_result", "missing_fields"],
            ),
            AgentCapability(
                name="triage",
                description="Score, prioritize, and route the submission",
                required_inputs=["extracted_data", "line_of_business"],
                produces=["triage_result"],
            ),
        ]

    # ------------------------------------------------------------------
    # Foundry-delegated prompt
    # ------------------------------------------------------------------

    def _build_prompt(self, task: dict[str, Any]) -> str:
        """Build a knowledge-enriched prompt via :func:`build_triage_prompt`."""
        from openinsure.agents.prompts import build_triage_prompt

        submission = task.get("submission", task)
        return build_triage_prompt(submission)

    # ------------------------------------------------------------------
    # Local fallback — minimal safe defaults
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return minimal defaults when Foundry is unavailable."""
        return {
            "classified_documents": [],
            "extracted_data": {},
            "validation_result": {
                "is_complete": False,
                "completeness_pct": 0.0,
                "present_fields": [],
                "missing_fields": [],
            },
            "triage_result": {
                "appetite_match": True,
                "risk_score": 0,
                "priority": 5,
                "decline_reason": None,
            },
            "confidence": 0.0,
            "ai_mode": "local_fallback",
            "ai_warning": "AI unavailable — manual triage required",
        }
