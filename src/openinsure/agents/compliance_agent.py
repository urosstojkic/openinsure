"""Compliance and audit agent for OpenInsure.

Performs regulatory compliance checking, audit trail generation,
bias monitoring across outcomes, and EU AI Act documentation generation.

When Foundry is available, all reasoning goes through GPT-5.1.
The local ``process()`` returns minimal defaults for graceful degradation.
"""

from decimal import Decimal
from typing import Any

import structlog

from openinsure.agents.base import (
    AgentCapability,
    AgentConfig,
    DecisionRecord,
    InsuranceAgent,
)

logger = structlog.get_logger()


class ComplianceAgent(InsuranceAgent):
    """Compliance checking, audit, and bias monitoring agent.

    In production all reasoning is performed by the Foundry-hosted agent.
    The local :meth:`process` returns safe minimal defaults so the system
    does not crash when Foundry is unavailable.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="compliance_agent",
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
                name="check_compliance",
                description="Check decision records for regulatory compliance",
                required_inputs=["decision_records"],
                produces=["compliance_result"],
            ),
            AgentCapability(
                name="generate_audit_report",
                description="Generate an audit trail report from decision records",
                required_inputs=["decision_records"],
                produces=["audit_report"],
            ),
            AgentCapability(
                name="check_bias",
                description="Monitor for bias across AI decision outcomes",
                required_inputs=["decision_records"],
                produces=["bias_report"],
            ),
            AgentCapability(
                name="generate_eu_ai_act_documentation",
                description="Generate EU AI Act compliance documentation",
                required_inputs=["decision_records", "system_info"],
                produces=["eu_ai_act_documentation"],
            ),
        ]

    # ------------------------------------------------------------------
    # Local fallback — minimal safe defaults
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return minimal defaults when Foundry is unavailable."""
        records = self._load_records(task)
        return {
            "compliant": False,
            "findings": [],
            "summary": {
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "rule_sets_evaluated": [],
            },
            "confidence": 0.0,
            "ai_mode": "local_fallback",
            "ai_warning": "AI unavailable — manual compliance review required",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_records(task: dict[str, Any]) -> list[dict[str, Any]]:
        """Load decision records from task payload.

        Accepts either raw dicts or :class:`DecisionRecord` instances.
        """
        raw = task.get("decision_records", [])
        records: list[dict[str, Any]] = []
        for r in raw:
            if isinstance(r, DecisionRecord):
                records.append(r.model_dump(mode="json"))
            elif isinstance(r, dict):
                records.append(r)
        return records
