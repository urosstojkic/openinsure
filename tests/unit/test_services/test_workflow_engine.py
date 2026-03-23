"""Tests for the multi-agent workflow engine."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openinsure.services.workflow_engine import (
    WORKFLOWS,
    WorkflowDefinition,
    WorkflowStep,
    _evaluate_condition,
    execute_workflow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_foundry_mock(responses: dict[str, dict[str, Any]] | None = None) -> MagicMock:
    """Build a mock FoundryAgentClient that returns canned responses per agent."""
    defaults: dict[str, dict[str, Any]] = {
        "openinsure-orchestrator": {
            "response": {
                "processing_path": "standard",
                "priority": "medium",
                "notes": "Standard processing",
                "confidence": 0.9,
            },
            "source": "foundry",
            "raw": "{}",
        },
        "openinsure-submission": {
            "response": {"appetite_match": "yes", "risk_score": 5, "priority": "medium", "confidence": 0.9},
            "source": "foundry",
            "raw": "{}",
        },
        "openinsure-underwriting": {
            "response": {"risk_score": 35, "recommended_premium": 12500, "confidence": 0.85, "conditions": []},
            "source": "foundry",
            "raw": "{}",
        },
        "openinsure-policy": {
            "response": {
                "recommendation": "issue",
                "coverage_adequate": True,
                "terms_complete": True,
                "notes": "All terms verified",
                "confidence": 0.92,
            },
            "source": "foundry",
            "raw": "{}",
        },
        "openinsure-compliance": {
            "response": {"compliant": True, "issues": []},
            "source": "foundry",
            "raw": "{}",
        },
        "openinsure-enrichment": {
            "response": {
                "composite_risk_score": 0.75,
                "risk_signals": [],
                "data_quality": "high",
                "confidence": 0.85,
            },
            "source": "foundry",
            "raw": "{}",
        },
        "openinsure-claims": {
            "response": {
                "coverage_confirmed": True,
                "severity_tier": "moderate",
                "initial_reserve": 50000,
                "fraud_score": 0.1,
                "confidence": 0.85,
            },
            "source": "foundry",
            "raw": "{}",
        },
    }
    if responses:
        defaults.update(responses)

    mock = MagicMock()

    async def _invoke(agent_name: str, _message: str) -> dict[str, Any]:
        return defaults.get(agent_name, {"response": "", "source": "fallback"})

    mock.invoke = AsyncMock(side_effect=_invoke)
    return mock


# ---------------------------------------------------------------------------
# Tests — workflow definitions
# ---------------------------------------------------------------------------


class TestWorkflowDefinitions:
    """Verify that the pre-defined workflows exist and have sensible structure."""

    def test_registry_contains_all_workflows(self) -> None:
        assert "new_business" in WORKFLOWS
        assert "claims_assessment" in WORKFLOWS
        assert "renewal" in WORKFLOWS

    def test_new_business_has_all_six_steps(self) -> None:
        wf = WORKFLOWS["new_business"]
        assert len(wf.steps) == 6
        names = [s.name for s in wf.steps]
        assert "orchestration" in names
        assert "enrichment" in names
        assert "intake" in names
        assert "underwriting" in names
        assert "policy_review" in names
        assert "compliance" in names

    def test_new_business_step_order(self) -> None:
        """Orchestration → enrichment → intake → underwriting → policy_review → compliance."""
        wf = WORKFLOWS["new_business"]
        names = [s.name for s in wf.steps]
        assert names.index("orchestration") < names.index("enrichment")
        assert names.index("enrichment") < names.index("intake")
        assert names.index("intake") < names.index("underwriting")
        assert names.index("underwriting") < names.index("policy_review")
        assert names.index("policy_review") < names.index("compliance")

    def test_new_business_agents_correct(self) -> None:
        wf = WORKFLOWS["new_business"]
        agent_map = {s.name: s.agent for s in wf.steps}
        assert agent_map["orchestration"] == "openinsure-orchestrator"
        assert agent_map["enrichment"] == "openinsure-enrichment"
        assert agent_map["intake"] == "openinsure-submission"
        assert agent_map["underwriting"] == "openinsure-underwriting"
        assert agent_map["policy_review"] == "openinsure-policy"
        assert agent_map["compliance"] == "openinsure-compliance"

    def test_underwriting_step_has_condition(self) -> None:
        wf = WORKFLOWS["new_business"]
        uw_step = next(s for s in wf.steps if s.name == "underwriting")
        assert uw_step.condition is not None
        assert "appetite_match" in uw_step.condition

    def test_claims_workflow_has_three_steps(self) -> None:
        wf = WORKFLOWS["claims_assessment"]
        assert len(wf.steps) == 3
        names = [s.name for s in wf.steps]
        assert "orchestration" in names
        assert "assessment" in names
        assert "compliance" in names

    def test_claims_agents_correct(self) -> None:
        wf = WORKFLOWS["claims_assessment"]
        agent_map = {s.name: s.agent for s in wf.steps}
        assert agent_map["orchestration"] == "openinsure-orchestrator"
        assert agent_map["assessment"] == "openinsure-claims"
        assert agent_map["compliance"] == "openinsure-compliance"

    def test_renewal_workflow_has_two_steps(self) -> None:
        wf = WORKFLOWS["renewal"]
        assert len(wf.steps) == 2


# ---------------------------------------------------------------------------
# Tests — condition evaluator
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    """Unit tests for _evaluate_condition."""

    def test_simple_match(self) -> None:
        ctx: dict[str, Any] = {"intake_result": {"appetite_match": "yes"}}
        assert _evaluate_condition("intake.appetite_match == 'yes'", ctx) is True

    def test_simple_mismatch(self) -> None:
        ctx: dict[str, Any] = {"intake_result": {"appetite_match": "no"}}
        assert _evaluate_condition("intake.appetite_match == 'yes'", ctx) is False

    def test_case_insensitive(self) -> None:
        ctx: dict[str, Any] = {"intake_result": {"appetite_match": "YES"}}
        assert _evaluate_condition("intake.appetite_match == 'yes'", ctx) is True

    def test_missing_key_returns_false(self) -> None:
        # Missing path resolves to "" which won't match the expected value
        assert _evaluate_condition("nonexistent.field == 'x'", {}) is False

    def test_malformed_condition_defaults_false(self) -> None:
        """Fail-closed: malformed conditions reject (safety default per #58)."""
        assert _evaluate_condition("this is not a real condition", {}) is False


# ---------------------------------------------------------------------------
# Tests — workflow execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExecuteWorkflow:
    """Integration-level tests for execute_workflow with mocked Foundry."""

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_new_business_happy_path(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        mock_get_fc.return_value = _make_foundry_mock()

        execution = await execute_workflow(
            "new_business",
            "sub-123",
            "submission",
            {"id": "sub-123", "applicant_name": "Test Corp"},
        )

        assert execution.status == "completed"
        assert execution.completed_at is not None
        step_names = [s["name"] for s in execution.steps_completed]
        # All 6 steps should be present
        assert "orchestration" in step_names
        assert "enrichment" in step_names
        assert "intake" in step_names
        assert "underwriting" in step_names
        assert "policy_review" in step_names
        assert "compliance" in step_names
        # All should be completed (not skipped/failed)
        completed_steps = [s for s in execution.steps_completed if s["status"] == "completed"]
        assert len(completed_steps) == 6

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_new_business_all_six_agents_invoked(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        """Verify all 6 distinct Foundry agents are called in new_business workflow."""
        mock = _make_foundry_mock()
        mock_get_fc.return_value = mock

        await execute_workflow("new_business", "sub-agents", "submission", {"id": "sub-agents"})

        invoked_agents = [call.args[0] for call in mock.invoke.call_args_list]
        assert "openinsure-orchestrator" in invoked_agents
        assert "openinsure-enrichment" in invoked_agents
        assert "openinsure-submission" in invoked_agents
        assert "openinsure-underwriting" in invoked_agents
        assert "openinsure-policy" in invoked_agents
        assert "openinsure-compliance" in invoked_agents

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_step_skipped_when_condition_not_met(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        """When triage says appetite_match='no', underwriting should be skipped."""
        mock_get_fc.return_value = _make_foundry_mock(
            {
                "openinsure-submission": {
                    "response": {"appetite_match": "no", "risk_score": 2},
                    "source": "foundry",
                    "raw": "{}",
                },
            }
        )

        execution = await execute_workflow(
            "new_business",
            "sub-456",
            "submission",
            {"id": "sub-456"},
        )

        assert execution.status == "completed"
        uw_step = next(s for s in execution.steps_completed if s["name"] == "underwriting")
        assert uw_step["status"] == "skipped"
        assert "Condition not met" in uw_step.get("reason", "")
        # Orchestration, intake, policy_review, compliance still ran
        orchestration = next(s for s in execution.steps_completed if s["name"] == "orchestration")
        assert orchestration["status"] == "completed"
        policy = next(s for s in execution.steps_completed if s["name"] == "policy_review")
        assert policy["status"] == "completed"

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_required_step_failure_aborts_workflow(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        """When a required step raises, the workflow should fail."""
        mock = _make_foundry_mock()

        async def _exploding_invoke(agent_name: str, _msg: str) -> dict:
            if agent_name == "openinsure-orchestrator":
                raise RuntimeError("Foundry unreachable")
            return {"response": {}, "source": "fallback"}

        mock.invoke = AsyncMock(side_effect=_exploding_invoke)
        mock_get_fc.return_value = mock

        execution = await execute_workflow("new_business", "sub-789", "submission", {})

        assert execution.status == "failed"
        assert "orchestration" in (execution.error or "")
        # Subsequent steps should NOT have been attempted
        step_names = [s["name"] for s in execution.steps_completed]
        assert "intake" not in step_names
        assert "underwriting" not in step_names

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_optional_step_failure_continues(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        """An optional step failure should not abort the workflow."""
        # Create a custom workflow with an optional step that fails
        failing_wf = WorkflowDefinition(
            name="test_optional",
            steps=[
                WorkflowStep("step_a", "openinsure-submission", "prompt A"),
                WorkflowStep("step_b", "openinsure-compliance", "prompt B", required=False),
            ],
        )

        mock = _make_foundry_mock()
        call_count = 0

        async def _partial_fail(agent_name: str, _msg: str) -> dict:
            nonlocal call_count
            call_count += 1
            if agent_name == "openinsure-compliance":
                raise RuntimeError("Compliance service down")
            return {"response": {"ok": True}, "source": "foundry", "raw": "{}"}

        mock.invoke = AsyncMock(side_effect=_partial_fail)
        mock_get_fc.return_value = mock

        # Temporarily register our test workflow
        from openinsure.services.workflow_engine import WORKFLOWS

        WORKFLOWS["test_optional"] = failing_wf
        try:
            execution = await execute_workflow("test_optional", "entity-1", "test", {})
            assert execution.status == "completed"  # NOT failed
            step_b = next(s for s in execution.steps_completed if s["name"] == "step_b")
            assert step_b["status"] == "failed"
        finally:
            del WORKFLOWS["test_optional"]

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_claims_workflow(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        mock = _make_foundry_mock()
        mock_get_fc.return_value = mock

        execution = await execute_workflow(
            "claims_assessment",
            "clm-100",
            "claim",
            {"id": "clm-100", "claim_type": "data_breach"},
        )

        assert execution.status == "completed"
        step_names = [s["name"] for s in execution.steps_completed]
        assert "orchestration" in step_names
        assert "assessment" in step_names
        assert "compliance" in step_names
        # Verify all 3 agents were invoked
        invoked_agents = [call.args[0] for call in mock.invoke.call_args_list]
        assert "openinsure-orchestrator" in invoked_agents
        assert "openinsure-claims" in invoked_agents
        assert "openinsure-compliance" in invoked_agents

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_renewal_workflow(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        mock_get_fc.return_value = _make_foundry_mock(
            {
                "openinsure-underwriting": {
                    "response": {"renewal_premium": 15000, "recommendation": "renew", "confidence": 0.9},
                    "source": "foundry",
                    "raw": "{}",
                },
            }
        )

        execution = await execute_workflow(
            "renewal",
            "pol-200",
            "policy",
            {"id": "pol-200", "total_premium": 12000},
        )

        assert execution.status == "completed"
        assert execution.context.get("assessment_result", {}).get("renewal_premium") == 15000

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_unknown_workflow_raises(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        with pytest.raises(ValueError, match="Unknown workflow"):
            await execute_workflow("nonexistent", "x", "x", {})

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_domain_events_published(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        mock_get_fc.return_value = _make_foundry_mock()

        await execute_workflow("claims_assessment", "clm-ev", "claim", {})

        event_types = [call.args[0] for call in mock_event.call_args_list]
        assert "workflow.claims_assessment.started" in event_types
        assert "workflow.claims_assessment.completed" in event_types
        # One step_completed per step (orchestration + assessment + compliance = 3)
        step_events = [e for e in event_types if "step_completed" in e]
        assert len(step_events) == 3

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_context_accumulates_across_steps(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        mock_get_fc.return_value = _make_foundry_mock()

        execution = await execute_workflow("new_business", "sub-ctx", "submission", {"id": "sub-ctx"})

        assert "orchestration_result" in execution.context
        assert "enrichment_result" in execution.context
        assert "intake_result" in execution.context
        assert "underwriting_result" in execution.context
        assert "policy_review_result" in execution.context
        assert "compliance_result" in execution.context

    @patch("openinsure.services.workflow_engine.publish_domain_event", new_callable=AsyncMock)
    @patch("openinsure.services.workflow_engine.get_foundry_client")
    async def test_execution_stored_in_history(self, mock_get_fc: MagicMock, mock_event: AsyncMock) -> None:
        from openinsure.services.workflow_engine import get_execution_by_id

        mock_get_fc.return_value = _make_foundry_mock()

        execution = await execute_workflow("claims_assessment", "clm-hist", "claim", {})

        found = get_execution_by_id(execution.id)
        assert found is not None
        assert found.id == execution.id
