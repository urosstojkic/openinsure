"""Tests for the InsuranceAgent base class."""

from typing import Any

import pytest

from openinsure.agents.base import (
    AgentCapability,
    AgentConfig,
    DecisionRecord,
    InsuranceAgent,
)


class _TestAgent(InsuranceAgent):
    """Concrete test agent that inherits from InsuranceAgent."""

    def __init__(self, config: AgentConfig, result: dict[str, Any] | None = None):
        super().__init__(config)
        self._result = result or {
            "confidence": 0.9,
            "result": "test_output",
            "reasoning": {"step": "test"},
        }

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="test_capability",
                description="A test capability",
                required_inputs=["input_data"],
                produces=["output_data"],
            )
        ]

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        if task.get("should_fail"):
            msg = "Simulated agent error"
            raise RuntimeError(msg)
        return self._result


class _LowConfidenceAgent(InsuranceAgent):
    """Agent that always returns low confidence."""

    @property
    def capabilities(self) -> list[AgentCapability]:
        return []

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        return {"confidence": 0.3, "result": "uncertain"}


def _make_config(**overrides) -> AgentConfig:
    """Helper to create agent config."""
    defaults = {
        "agent_id": "test-agent",
        "agent_version": "0.1.0",
        "escalation_threshold": 0.7,
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


class TestAgentConfig:
    """Test agent configuration."""

    def test_agent_config(self):
        config = _make_config()
        assert config.agent_id == "test-agent"
        assert config.agent_version == "0.1.0"
        assert config.escalation_threshold == 0.7

    def test_agent_config_defaults(self):
        config = AgentConfig(agent_id="minimal-agent")
        assert config.model_deployment == "gpt-4o"
        assert config.temperature == 0.1
        assert config.max_tokens == 4096
        assert config.auto_execute is False

    def test_agent_config_custom(self):
        config = AgentConfig(
            agent_id="custom-agent",
            model_deployment="gpt-4o-mini",
            temperature=0.5,
            max_tokens=8192,
            escalation_threshold=0.8,
        )
        assert config.model_deployment == "gpt-4o-mini"
        assert config.temperature == 0.5
        assert config.escalation_threshold == 0.8


class TestDecisionRecordCreation:
    """Test DecisionRecord creation."""

    def test_decision_record_creation(self):
        record = DecisionRecord(
            agent_id="test-agent",
            agent_version="0.1.0",
            model_used="gpt-4o",
            model_version="2026-03-01",
            decision_type="test_decision",
            confidence=0.85,
        )
        assert record.agent_id == "test-agent"
        assert record.confidence == 0.85
        assert record.decision_id is not None
        assert record.timestamp is not None

    def test_decision_record_defaults(self):
        record = DecisionRecord(
            agent_id="test",
            agent_version="0.1.0",
            model_used="gpt-4o",
            model_version="2026-03-01",
            decision_type="test",
            confidence=0.5,
        )
        assert record.input_summary == {}
        assert record.output == {}
        assert record.error is None
        assert record.execution_time_ms == 0


class TestAgentExecuteSuccess:
    """Test successful agent execution."""

    @pytest.mark.asyncio
    async def test_agent_execute_success(self):
        config = _make_config()
        agent = _TestAgent(config)
        result, decision = await agent.execute({"type": "test_task"})

        assert result["confidence"] == 0.9
        assert result["result"] == "test_output"
        assert decision.confidence == 0.9
        assert decision.error is None
        assert decision.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_agent_returns_decision_record(self):
        agent = _TestAgent(_make_config())
        _result, decision = await agent.execute({"type": "test"})
        assert isinstance(decision, DecisionRecord)
        assert decision.agent_id == "test-agent"


class TestAgentExecuteErrorHandling:
    """Test agent error handling."""

    @pytest.mark.asyncio
    async def test_agent_execute_error_handling(self):
        agent = _TestAgent(_make_config())
        result, decision = await agent.execute({"type": "test", "should_fail": True})

        assert "error" in result
        assert decision.error is not None
        assert "Simulated agent error" in decision.error
        assert decision.confidence == 0.0
        assert decision.human_oversight["required"] is True
        assert decision.human_oversight["reason"] == "agent_error"


class TestEscalationBelowThreshold:
    """Test escalation when confidence is below threshold."""

    @pytest.mark.asyncio
    async def test_escalation_below_threshold(self):
        config = _make_config(escalation_threshold=0.7)
        agent = _LowConfidenceAgent(config)
        result, decision = await agent.execute({"type": "test"})

        assert decision.confidence == 0.3
        assert decision.human_oversight["required"] is True
        assert decision.human_oversight["reason"] == "confidence_below_threshold"
        assert result.get("escalation_required") is True


class TestNoEscalationAboveThreshold:
    """Test no escalation when confidence is above threshold."""

    @pytest.mark.asyncio
    async def test_no_escalation_above_threshold(self):
        config = _make_config(escalation_threshold=0.7)
        agent = _TestAgent(config, result={"confidence": 0.9, "result": "ok"})
        result, decision = await agent.execute({"type": "test"})

        assert decision.confidence == 0.9
        assert decision.human_oversight["required"] is False
        assert result.get("escalation_required") is None


class TestDecisionRecordTiming:
    """Test decision record timing."""

    @pytest.mark.asyncio
    async def test_decision_record_timing(self):
        agent = _TestAgent(_make_config())
        _, decision = await agent.execute({"type": "test"})

        assert decision.execution_time_ms >= 0
        assert decision.timestamp is not None

    @pytest.mark.asyncio
    async def test_timing_on_error(self):
        agent = _TestAgent(_make_config())
        _, decision = await agent.execute({"type": "test", "should_fail": True})
        assert decision.execution_time_ms >= 0


class TestDecisionHistoryTracking:
    """Test decision history tracking."""

    @pytest.mark.asyncio
    async def test_decision_history_tracking(self):
        agent = _TestAgent(_make_config())

        await agent.execute({"type": "task_1"})
        await agent.execute({"type": "task_2"})
        await agent.execute({"type": "task_3"})

        assert len(agent.decision_history) == 3
        assert all(isinstance(d, DecisionRecord) for d in agent.decision_history)

    @pytest.mark.asyncio
    async def test_history_includes_errors(self):
        agent = _TestAgent(_make_config())

        await agent.execute({"type": "success"})
        await agent.execute({"type": "fail", "should_fail": True})

        assert len(agent.decision_history) == 2
        assert agent.decision_history[0].error is None
        assert agent.decision_history[1].error is not None

    @pytest.mark.asyncio
    async def test_history_starts_empty(self):
        agent = _TestAgent(_make_config())
        assert len(agent.decision_history) == 0
