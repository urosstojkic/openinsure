"""Data-driven workflow template registry.

Loads workflow definitions from the ``workflow_templates`` / ``workflow_steps``
tables, falling back to in-memory defaults when no database is available or
no product-specific template exists.

See migration ``025_workflow_templates.sql`` for the schema.
"""

from __future__ import annotations

from typing import Any

import structlog

from openinsure.services.workflow_engine import WorkflowDefinition, WorkflowStep

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# In-memory default workflows — used as fallback when DB is unavailable
# or no matching template exists.
# ---------------------------------------------------------------------------

_DEFAULT_NEW_BUSINESS_STEPS: list[dict[str, Any]] = [
    {
        "step_name": "orchestration",
        "step_order": 1,
        "agent_name": "openinsure-orchestrator",
        "depends_on": None,
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "enrichment",
        "step_order": 2,
        "agent_name": "openinsure-enrichment",
        "depends_on": "orchestration",
        "is_optional": True,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "intake",
        "step_order": 3,
        "agent_name": "openinsure-submission",
        "depends_on": "orchestration",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "underwriting",
        "step_order": 4,
        "agent_name": "openinsure-underwriting",
        "depends_on": "intake",
        "is_optional": False,
        "skip_condition": "intake.appetite_match == 'yes'",
        "timeout_seconds": 60,
    },
    {
        "step_name": "compliance",
        "step_order": 5,
        "agent_name": "openinsure-compliance",
        "depends_on": "intake,underwriting",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
]

_DEFAULT_CLAIMS_STEPS: list[dict[str, Any]] = [
    {
        "step_name": "orchestration",
        "step_order": 1,
        "agent_name": "openinsure-orchestrator",
        "depends_on": None,
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "assessment",
        "step_order": 2,
        "agent_name": "openinsure-claims",
        "depends_on": "orchestration",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "compliance",
        "step_order": 3,
        "agent_name": "openinsure-compliance",
        "depends_on": "orchestration,assessment",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
]

_DEFAULT_RENEWAL_STEPS: list[dict[str, Any]] = [
    {
        "step_name": "orchestration",
        "step_order": 1,
        "agent_name": "openinsure-orchestrator",
        "depends_on": None,
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "assessment",
        "step_order": 2,
        "agent_name": "openinsure-underwriting",
        "depends_on": "orchestration",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "policy_review",
        "step_order": 3,
        "agent_name": "openinsure-policy",
        "depends_on": "assessment",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
    {
        "step_name": "compliance",
        "step_order": 4,
        "agent_name": "openinsure-compliance",
        "depends_on": "assessment,policy_review",
        "is_optional": False,
        "skip_condition": None,
        "timeout_seconds": 60,
    },
]

_DEFAULT_WORKFLOWS: dict[str, list[dict[str, Any]]] = {
    "new_business": _DEFAULT_NEW_BUSINESS_STEPS,
    "claims": _DEFAULT_CLAIMS_STEPS,
    "claims_assessment": _DEFAULT_CLAIMS_STEPS,  # alias kept for backward compat
    "renewal": _DEFAULT_RENEWAL_STEPS,
}


def _step_row_to_workflow_step(row: dict[str, Any]) -> WorkflowStep:
    """Convert a step row (from DB or in-memory defaults) to a ``WorkflowStep``."""
    deps_raw = row.get("depends_on") or ""
    depends_on = [d.strip() for d in deps_raw.split(",") if d.strip()] if deps_raw else []

    return WorkflowStep(
        name=row["step_name"],
        agent=row.get("agent_name") or "openinsure-orchestrator",
        prompt_template="",  # prompts are resolved at execution time via build_prompt_for_step
        required=not bool(row.get("is_optional", False)),
        condition=row.get("skip_condition") or None,
        depends_on=depends_on,
    )


def _build_definition(workflow_type: str, step_rows: list[dict[str, Any]]) -> WorkflowDefinition:
    """Build a ``WorkflowDefinition`` from ordered step rows."""
    sorted_rows = sorted(step_rows, key=lambda r: r.get("step_order", 0))
    steps = [_step_row_to_workflow_step(row) for row in sorted_rows]
    return WorkflowDefinition(name=workflow_type, steps=steps)


async def get_workflow_for_product(
    product_id: str | None,
    workflow_type: str,
) -> WorkflowDefinition:
    """Return the workflow definition for a product + type.

    Resolution order:
    1. Product-specific active template from the database
    2. Default (product_id IS NULL) active template from the database
    3. In-memory fallback constants

    This ensures the engine always has a workflow, even without a database.
    """
    # Attempt DB lookup
    try:
        from openinsure.infrastructure.factory import get_database_adapter

        db = get_database_adapter()
        if db:
            step_rows = await _load_from_db(db, product_id, workflow_type)
            if step_rows:
                logger.info(
                    "workflow_registry.loaded_from_db",
                    product_id=product_id,
                    workflow_type=workflow_type,
                    steps=len(step_rows),
                )
                return _build_definition(workflow_type, step_rows)
    except Exception:
        logger.debug("workflow_registry.db_lookup_failed", exc_info=True)

    # In-memory fallback
    default_steps = _DEFAULT_WORKFLOWS.get(workflow_type)
    if default_steps is None:
        raise ValueError(f"Unknown workflow type: {workflow_type}")

    logger.info(
        "workflow_registry.using_defaults",
        workflow_type=workflow_type,
        steps=len(default_steps),
    )
    return _build_definition(workflow_type, default_steps)


async def _load_from_db(
    db: Any,
    product_id: str | None,
    workflow_type: str,
) -> list[dict[str, Any]]:
    """Load workflow steps from the database.

    Tries product-specific first, then default (product_id IS NULL).
    """
    # Try product-specific template
    if product_id:
        rows = await _query_steps(db, product_id, workflow_type)
        if rows:
            return rows

    # Fall back to default template
    return await _query_steps(db, None, workflow_type)


async def _query_steps(
    db: Any,
    product_id: str | None,
    workflow_type: str,
) -> list[dict[str, Any]]:
    """Query workflow_steps joined with workflow_templates."""
    if product_id:
        query = (
            "SELECT s.step_name, s.step_order, s.agent_name, s.is_parallel, "
            "s.depends_on, s.timeout_seconds, s.is_optional, s.skip_condition, s.prompt_key "
            "FROM workflow_steps s "
            "INNER JOIN workflow_templates t ON s.template_id = t.id "
            "WHERE t.product_id = ? AND t.workflow_type = ? AND t.status = 'active' "
            "ORDER BY s.step_order"
        )
        params = [product_id, workflow_type]
    else:
        query = (
            "SELECT s.step_name, s.step_order, s.agent_name, s.is_parallel, "
            "s.depends_on, s.timeout_seconds, s.is_optional, s.skip_condition, s.prompt_key "
            "FROM workflow_steps s "
            "INNER JOIN workflow_templates t ON s.template_id = t.id "
            "WHERE t.product_id IS NULL AND t.workflow_type = ? AND t.status = 'active' "
            "ORDER BY s.step_order"
        )
        params = [workflow_type]

    try:
        result = await db.execute_query(query, params)
        return result if result else []
    except Exception:
        logger.debug("workflow_registry.query_failed", exc_info=True)
        return []


def get_default_workflow_types() -> list[str]:
    """Return the list of supported default workflow types."""
    return ["new_business", "claims", "renewal"]


def get_default_steps(workflow_type: str) -> list[dict[str, Any]]:
    """Return the in-memory default step definitions for a workflow type.

    Useful for seeding, testing, or displaying available templates.
    """
    steps = _DEFAULT_WORKFLOWS.get(workflow_type)
    if steps is None:
        raise ValueError(f"Unknown workflow type: {workflow_type}")
    return list(steps)
