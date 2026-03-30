"""Tests for the workflow registry (data-driven workflow templates).

Covers:
- Default in-memory workflow definitions (new_business, claims, renewal)
- get_workflow_for_product fallback logic
- Step row → WorkflowStep conversion
- get_default_steps and get_default_workflow_types helpers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from openinsure.services.workflow_registry import (
    _build_definition,
    _step_row_to_workflow_step,
    get_default_steps,
    get_default_workflow_types,
    get_workflow_for_product,
)


class TestDefaultWorkflows:
    """Verify in-memory default workflow configurations."""

    def test_default_workflow_types(self) -> None:
        types = get_default_workflow_types()
        assert "new_business" in types
        assert "claims" in types
        assert "renewal" in types

    def test_new_business_has_five_steps(self) -> None:
        steps = get_default_steps("new_business")
        assert len(steps) == 5
        names = [s["step_name"] for s in steps]
        assert names == ["orchestration", "enrichment", "intake", "underwriting", "compliance"]

    def test_claims_has_three_steps(self) -> None:
        steps = get_default_steps("claims")
        assert len(steps) == 3
        names = [s["step_name"] for s in steps]
        assert names == ["orchestration", "assessment", "compliance"]

    def test_renewal_has_four_steps(self) -> None:
        steps = get_default_steps("renewal")
        assert len(steps) == 4
        names = [s["step_name"] for s in steps]
        assert names == ["orchestration", "assessment", "policy_review", "compliance"]

    def test_unknown_workflow_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown workflow type"):
            get_default_steps("nonexistent")

    def test_enrichment_is_optional(self) -> None:
        steps = get_default_steps("new_business")
        enrichment = next(s for s in steps if s["step_name"] == "enrichment")
        assert enrichment["is_optional"] is True

    def test_underwriting_has_condition(self) -> None:
        steps = get_default_steps("new_business")
        uw = next(s for s in steps if s["step_name"] == "underwriting")
        assert uw["skip_condition"] is not None
        assert "appetite_match" in uw["skip_condition"]


class TestStepConversion:
    """Test _step_row_to_workflow_step conversion."""

    def test_basic_conversion(self) -> None:
        row = {
            "step_name": "intake",
            "agent_name": "openinsure-submission",
            "depends_on": "orchestration",
            "is_optional": False,
            "skip_condition": None,
        }
        step = _step_row_to_workflow_step(row)
        assert step.name == "intake"
        assert step.agent == "openinsure-submission"
        assert step.depends_on == ["orchestration"]
        assert step.required is True
        assert step.condition is None

    def test_multiple_dependencies(self) -> None:
        row = {
            "step_name": "compliance",
            "agent_name": "openinsure-compliance",
            "depends_on": "intake,underwriting",
            "is_optional": False,
            "skip_condition": None,
        }
        step = _step_row_to_workflow_step(row)
        assert step.depends_on == ["intake", "underwriting"]

    def test_no_dependencies(self) -> None:
        row = {
            "step_name": "orchestration",
            "agent_name": "openinsure-orchestrator",
            "depends_on": None,
            "is_optional": False,
            "skip_condition": None,
        }
        step = _step_row_to_workflow_step(row)
        assert step.depends_on == []

    def test_optional_step(self) -> None:
        row = {
            "step_name": "enrichment",
            "agent_name": "openinsure-enrichment",
            "depends_on": "orchestration",
            "is_optional": True,
            "skip_condition": None,
        }
        step = _step_row_to_workflow_step(row)
        assert step.required is False

    def test_with_condition(self) -> None:
        row = {
            "step_name": "underwriting",
            "agent_name": "openinsure-underwriting",
            "depends_on": "intake",
            "is_optional": False,
            "skip_condition": "intake.appetite_match == 'yes'",
        }
        step = _step_row_to_workflow_step(row)
        assert step.condition == "intake.appetite_match == 'yes'"


class TestBuildDefinition:
    """Test _build_definition constructs a proper WorkflowDefinition."""

    def test_builds_sorted_definition(self) -> None:
        rows = [
            {
                "step_name": "compliance",
                "step_order": 3,
                "agent_name": "c",
                "depends_on": "b",
                "is_optional": False,
                "skip_condition": None,
            },
            {
                "step_name": "orchestration",
                "step_order": 1,
                "agent_name": "a",
                "depends_on": None,
                "is_optional": False,
                "skip_condition": None,
            },
            {
                "step_name": "assessment",
                "step_order": 2,
                "agent_name": "b",
                "depends_on": "a",
                "is_optional": False,
                "skip_condition": None,
            },
        ]
        defn = _build_definition("test_workflow", rows)
        assert defn.name == "test_workflow"
        assert len(defn.steps) == 3
        assert [s.name for s in defn.steps] == ["orchestration", "assessment", "compliance"]


class TestGetWorkflowForProduct:
    """Test the main registry lookup function."""

    @pytest.mark.asyncio
    async def test_fallback_to_defaults_when_no_db(self) -> None:
        """Without a database adapter, should use in-memory defaults."""
        with patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None):
            defn = await get_workflow_for_product(None, "new_business")
        assert defn.name == "new_business"
        assert len(defn.steps) == 5

    @pytest.mark.asyncio
    async def test_fallback_to_defaults_on_db_error(self) -> None:
        """Database errors should fall back to in-memory defaults."""
        mock_db = AsyncMock()
        mock_db.execute_query.side_effect = Exception("DB down")
        with patch("openinsure.infrastructure.factory.get_database_adapter", return_value=mock_db):
            defn = await get_workflow_for_product(None, "claims")
        assert defn.name == "claims"
        assert len(defn.steps) == 3

    @pytest.mark.asyncio
    async def test_unknown_workflow_raises(self) -> None:
        with patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None):
            with pytest.raises(ValueError, match="Unknown workflow type"):
                await get_workflow_for_product(None, "nonexistent")

    @pytest.mark.asyncio
    async def test_claims_assessment_alias(self) -> None:
        """claims_assessment should resolve to the same steps as claims."""
        with patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None):
            defn = await get_workflow_for_product(None, "claims_assessment")
        assert defn.name == "claims_assessment"
        assert len(defn.steps) == 3

    @pytest.mark.asyncio
    async def test_renewal_has_four_steps(self) -> None:
        with patch("openinsure.infrastructure.factory.get_database_adapter", return_value=None):
            defn = await get_workflow_for_product(None, "renewal")
        assert len(defn.steps) == 4
        step_names = [s.name for s in defn.steps]
        assert "policy_review" in step_names

    @pytest.mark.asyncio
    async def test_product_specific_from_db(self) -> None:
        """When DB returns product-specific steps, use them."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [
            {
                "step_name": "custom_intake",
                "step_order": 1,
                "agent_name": "openinsure-submission",
                "is_parallel": False,
                "depends_on": None,
                "timeout_seconds": 30,
                "is_optional": False,
                "skip_condition": None,
                "prompt_key": "custom",
            },
            {
                "step_name": "custom_review",
                "step_order": 2,
                "agent_name": "openinsure-underwriting",
                "is_parallel": False,
                "depends_on": "custom_intake",
                "timeout_seconds": 60,
                "is_optional": False,
                "skip_condition": None,
                "prompt_key": "custom_review",
            },
        ]
        with patch("openinsure.infrastructure.factory.get_database_adapter", return_value=mock_db):
            defn = await get_workflow_for_product("product-123", "new_business")
        assert len(defn.steps) == 2
        assert defn.steps[0].name == "custom_intake"
        assert defn.steps[1].name == "custom_review"
        assert defn.steps[1].depends_on == ["custom_intake"]
