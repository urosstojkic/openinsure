"""Document processing agent for OpenInsure.

Handles document classification, structured data extraction from
insurance documents, and document generation (quotes, policies,
certificates).

When Foundry is available the prompt is built by
:func:`build_document_prompt` which injects coverage knowledge and
standard exclusions from the knowledge graph.  The local ``process()``
returns minimal defaults for graceful degradation.
"""

from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent
from openinsure.domain.limits import PLATFORM_LIMITS

logger = structlog.get_logger()


class DocumentAgent(InsuranceAgent):
    """Document classification, extraction, and generation agent.

    In production all reasoning is performed by the Foundry-hosted agent
    using the knowledge-enriched prompt from
    ``prompts.build_document_prompt``.  The local :meth:`process` returns
    safe minimal defaults so the system does not crash when Foundry is
    unavailable.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="document_agent",
                agent_version="0.1.0",
                authority_limit=PLATFORM_LIMITS.agents.document_agent,
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="classify_document",
                description="Classify an insurance document by type",
                required_inputs=["document"],
                produces=["document_type", "classification_confidence"],
            ),
            AgentCapability(
                name="extract_data",
                description="Extract structured data from an insurance document",
                required_inputs=["document", "document_type"],
                produces=["extracted_data"],
            ),
            AgentCapability(
                name="generate_document",
                description="Generate an insurance document from structured data",
                required_inputs=["document_type", "data"],
                produces=["document_url", "document_id"],
            ),
        ]

    # ------------------------------------------------------------------
    # Foundry-delegated prompt
    # ------------------------------------------------------------------

    def _build_prompt(self, task: dict[str, Any]) -> str:
        """Build a knowledge-enriched prompt via :func:`build_document_prompt`."""
        from openinsure.agents.prompts import build_document_prompt

        policy = task.get("policy", {})
        submission = task.get("submission", {})
        doc_type = task.get("document_type", task.get("type", "declaration"))
        return build_document_prompt(policy, submission, doc_type)

    # ------------------------------------------------------------------
    # Local fallback — minimal safe defaults
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return minimal defaults when Foundry is unavailable."""
        task_type = task.get("type", "classify")
        if task_type == "extract":
            return {
                "document_type": task.get("document_type", "unknown"),
                "extracted_data": {},
                "extraction_completeness": 0.0,
                "missing_fields": [],
                "confidence": 0.0,
                "ai_mode": "local_fallback",
                "ai_warning": "AI unavailable — manual document extraction required",
            }
        if task_type == "generate":
            return {
                "document_id": None,
                "document_type": task.get("document_type", "unknown"),
                "confidence": 0.0,
                "ai_mode": "local_fallback",
                "ai_warning": "AI unavailable — document generation unavailable",
            }
        # Default: classify
        return {
            "document_type": "unknown",
            "display_name": "unknown",
            "classification_confidence": 0.0,
            "expected_fields": [],
            "confidence": 0.0,
            "ai_mode": "local_fallback",
            "ai_warning": "AI unavailable — manual document classification required",
        }
