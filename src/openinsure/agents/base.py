"""Base agent class for OpenInsure AI agents.

Every agent in OpenInsure inherits from InsuranceAgent. The base class provides:
- Decision record logging (EU AI Act compliance)
- Structured logging
- Error handling with retry logic
- Model selection via Foundry Model Router
- Memory management
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class DecisionRecord(BaseModel):
    """EU AI Act compliant decision record.

    Every AI decision in OpenInsure produces one of these records.
    Required for: Art. 12 (Record-Keeping), Art. 13 (Transparency),
    Art. 14 (Human Oversight).
    """

    decision_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_id: str
    agent_version: str
    model_used: str
    model_version: str
    decision_type: str
    input_summary: dict[str, Any] = Field(default_factory=dict)
    data_sources_used: list[str] = Field(default_factory=list)
    knowledge_graph_queries: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    reasoning: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fairness_metrics: dict[str, Any] = Field(default_factory=dict)
    human_oversight: dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: int = 0
    error: str | None = None


class AgentCapability(BaseModel):
    """Describes what an agent can do."""

    name: str
    description: str
    required_inputs: list[str]
    produces: list[str]


class AgentConfig(BaseModel):
    """Configuration for an insurance agent."""

    agent_id: str
    agent_version: str = "0.1.0"
    model_deployment: str = "gpt-5.2"
    temperature: float = 0.1
    max_tokens: int = 4096
    authority_limit: Decimal = Decimal("0")  # Max value agent can authorize
    auto_execute: bool = False  # Whether agent can execute without human approval
    escalation_threshold: float = 0.7  # Confidence below this triggers escalation


class InsuranceAgent(ABC):
    """Base class for all OpenInsure AI agents.

    Implements the core agent contract:
    1. Receive task
    2. Query knowledge graph for relevant rules
    3. Reason over task + knowledge + data
    4. Execute action or escalate
    5. Log everything as DecisionRecord
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.decision_history: list[DecisionRecord] = []
        self.logger = structlog.get_logger().bind(agent_id=config.agent_id)

    @property
    @abstractmethod
    def capabilities(self) -> list[AgentCapability]:
        """List of capabilities this agent provides."""
        ...

    @abstractmethod
    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process a task and return results.

        Subclasses implement domain-specific logic here.
        """
        ...

    async def execute(self, task: dict[str, Any]) -> tuple[dict[str, Any], DecisionRecord]:
        """Execute via Foundry if available, otherwise fall back to local.

        This is the primary entry point — Foundry-first by design.
        """
        from openinsure.agents.foundry_client import get_foundry_client

        foundry = get_foundry_client()

        if foundry.is_available and self.config.model_deployment:
            # Build prompt from task
            prompt = self._build_prompt(task)
            foundry_result = await foundry.invoke(
                f"openinsure-{self.config.agent_id.split('-')[0]}",
                prompt,
            )
            if foundry_result.get("source") == "foundry":
                # Wrap Foundry response in standard format
                result = foundry_result.get("response", {})
                if isinstance(result, str):
                    result = {"output": result}
                result["source"] = "foundry"
                result["ai_mode"] = "foundry"
                result["confidence"] = result.get("confidence", 0.8)
                # Create decision record
                decision = DecisionRecord(
                    agent_id=self.config.agent_id,
                    agent_version=self.config.agent_version,
                    model_used=self.config.model_deployment,
                    model_version="2026-03-01",
                    decision_type=self._get_decision_type(task),
                    input_summary=self._summarize_input(task),
                    output=self._summarize_output(result),
                    confidence=result.get("confidence", 0.8),
                    reasoning={"source": "foundry", "raw": foundry_result.get("raw", "")[:500]},
                )
                decision.human_oversight = {
                    "required": decision.confidence < self.config.escalation_threshold,
                    "reason": "foundry_assessment",
                    "overridden": False,
                }
                self.decision_history.append(decision)
                return result, decision

        # Fallback to local processing
        return await self.execute_local(task)

    async def execute_local(self, task: dict[str, Any]) -> tuple[dict[str, Any], DecisionRecord]:
        """Execute locally with full decision record logging.

        This is the fallback path when Foundry is unavailable. Results
        are tagged with ``ai_mode = "local_fallback"`` so callers can
        distinguish AI-powered responses from stub defaults.
        """
        start_time = datetime.now(UTC)
        decision = DecisionRecord(
            agent_id=self.config.agent_id,
            agent_version=self.config.agent_version,
            model_used=self.config.model_deployment,
            model_version="2026-03-01",
            decision_type=self._get_decision_type(task),
            input_summary=self._summarize_input(task),
        )

        try:
            self.logger.info("agent.task.start", task_type=task.get("type"))
            result = await self.process(task)

            # Tag local-fallback results so callers know AI was not used
            result.setdefault("ai_mode", "local_fallback")
            if result["ai_mode"] == "local_fallback":
                result.setdefault("ai_warning", "Running without AI — Foundry unavailable")

            decision.output = self._summarize_output(result)
            decision.confidence = result.get("confidence", 0.0)
            decision.reasoning = result.get("reasoning", {})
            decision.data_sources_used = result.get("data_sources", [])
            decision.knowledge_graph_queries = result.get("knowledge_queries", [])

            # Check if escalation is needed
            if decision.confidence < self.config.escalation_threshold:
                decision.human_oversight = {
                    "required": True,
                    "reason": "confidence_below_threshold",
                    "threshold": self.config.escalation_threshold,
                    "overridden": False,
                }
                result["escalation_required"] = True
                self.logger.warning("agent.escalation", confidence=decision.confidence)
            else:
                decision.human_oversight = {
                    "required": False,
                    "reason": "within_auto_authority",
                    "overridden": False,
                }

            self.logger.info("agent.task.complete", confidence=decision.confidence)

        except Exception as e:
            decision.error = str(e)
            decision.confidence = 0.0
            decision.human_oversight = {
                "required": True,
                "reason": "agent_error",
                "overridden": False,
            }
            self.logger.exception("agent.task.error", error=str(e))
            result = {"error": str(e), "escalation_required": True}

        finally:
            end_time = datetime.now(UTC)
            decision.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            self.decision_history.append(decision)

        return result, decision

    def _build_prompt(self, task: dict[str, Any]) -> str:
        """Build a prompt string from the task dict."""
        parts = [f"Process this {task.get('type', 'unknown')} task. Respond with JSON."]
        for key, val in task.items():
            if key != "raw_data" and val is not None:
                parts.append(f"{key}: {val}")
        return "\n".join(parts)

    def _get_decision_type(self, task: dict[str, Any]) -> str:
        """Derive decision type from task."""
        return f"{self.config.agent_id}_{task.get('type', 'unknown')}"

    def _summarize_input(self, task: dict[str, Any]) -> dict[str, Any]:
        """Create a summary of inputs for the decision record."""
        return {k: str(v)[:200] for k, v in task.items() if k != "raw_data"}

    def _summarize_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """Create a summary of outputs for the decision record."""
        return {k: str(v)[:200] for k, v in result.items() if k not in ("raw_data", "reasoning")}
