"""Document processing agent for OpenInsure.

Handles document classification, structured data extraction from
insurance documents, and document generation (quotes, policies,
certificates).

When Foundry is available, all reasoning goes through GPT-5.1.
The local ``process()`` returns minimal defaults for graceful degradation.
"""

from decimal import Decimal
from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent

logger = structlog.get_logger()


class DocumentAgent(InsuranceAgent):
    """Document classification, extraction, and generation agent.

    In production all reasoning is performed by the Foundry-hosted agent.
    The local :meth:`process` returns safe minimal defaults so the system
    does not crash when Foundry is unavailable.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="document_agent",
                agent_version="0.1.0",
                authority_limit=Decimal("0"),
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
