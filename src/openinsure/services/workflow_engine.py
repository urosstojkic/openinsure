"""Multi-agent workflow engine for OpenInsure.

Defines insurance workflows as step sequences, executes them through
Foundry agents, tracks state, and handles errors/escalations.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from openinsure.agents.foundry_client import get_foundry_client
from openinsure.services.event_publisher import publish_domain_event

logger = structlog.get_logger()


class WorkflowStep:
    """A single step in a workflow."""

    def __init__(
        self,
        name: str,
        agent: str,
        prompt_template: str,
        required: bool = True,
        condition: str | None = None,
        depends_on: list[str] | None = None,
    ):
        self.name = name
        self.agent = agent
        self.prompt_template = prompt_template
        self.required = required
        self.condition = condition  # e.g., "intake.appetite_match == 'yes'"
        self.depends_on: list[str] = depends_on or []


class WorkflowDefinition:
    """Defines a multi-agent workflow as a sequence of steps."""

    def __init__(self, name: str, steps: list[WorkflowStep]):
        self.name = name
        self.steps = steps


class WorkflowExecution:
    """Tracks the execution of a workflow instance."""

    def __init__(self, workflow_name: str, entity_id: str, entity_type: str):
        self.id = str(uuid4())
        self.workflow_name = workflow_name
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.status = "running"  # running, completed, failed, escalated
        self.steps_completed: list[dict[str, Any]] = []
        self.steps_remaining: list[str] = []
        self.context: dict[str, Any] = {}  # accumulated data from steps
        self.started_at = datetime.now(UTC).isoformat()
        self.completed_at: str | None = None
        self.error: str | None = None


# ---------------------------------------------------------------------------
# Workflow definitions
# ---------------------------------------------------------------------------

NEW_BUSINESS_WORKFLOW = WorkflowDefinition(
    name="new_business",
    steps=[
        WorkflowStep(
            name="orchestration",
            agent="openinsure-orchestrator",
            prompt_template=(
                "You are coordinating a new business submission workflow. "
                "Review the submission, determine the processing path, and "
                "set priorities for downstream agents.\n"
                'Respond with JSON: {{"processing_path": "standard/expedited/referral", '
                '"priority": "high/medium/low", "notes": "...", "confidence": 0.0-1.0}}\n\n'
                "Submission: {submission_data}"
            ),
            depends_on=[],
        ),
        WorkflowStep(
            name="enrichment",
            agent="openinsure-enrichment",
            prompt_template=(
                "Enrich this submission with external data. Query security ratings, "
                "firmographics, and breach history providers.\n"
                'Respond with JSON: {{"composite_risk_score": 0.0-1.0, '
                '"risk_signals": [...], "data_quality": "high/medium/low", "confidence": 0.0-1.0}}\n\n'
                "Submission: {submission_data}\nOrchestration: {orchestration_result}"
            ),
            required=False,
            depends_on=["orchestration"],
        ),
        WorkflowStep(
            name="intake",
            agent="openinsure-submission",
            prompt_template=(
                "Triage this cyber insurance submission. Our appetite: IT/Tech (SIC 7xxx), "
                "Financial (SIC 6xxx), Professional Services. Revenue $500K-$50M. "
                "Security maturity 4+/10. Max 3 prior incidents.\n"
                'Respond with JSON: {{"appetite_match": "yes/no", "risk_score": N, '
                '"priority": "high/medium/low", "confidence": 0.0-1.0}}\n\n'
                "Submission: {submission_data}\nOrchestration: {orchestration_result}"
            ),
            depends_on=["orchestration"],
        ),
        WorkflowStep(
            name="underwriting",
            agent="openinsure-underwriting",
            prompt_template=(
                "Price this cyber submission. Base: $1.50/$1000 revenue. "
                "Adjust for industry, security, incidents.\n"
                'Respond with JSON: {{"risk_score": N, "recommended_premium": N, '
                '"confidence": 0.0-1.0, "conditions": [...]}}\n\n'
                "Submission: {submission_data}\nTriage: {intake_result}"
            ),
            condition="intake.appetite_match == 'yes'",
            depends_on=["intake"],
        ),
        WorkflowStep(
            name="policy_review",
            agent="openinsure-policy",
            prompt_template=(
                "Review underwriting terms and prepare policy issuance recommendation. "
                "Verify coverages are appropriate, terms are complete, and "
                "pricing is within guidelines.\n"
                'Respond with JSON: {{"recommendation": "issue/refer/decline", '
                '"coverage_adequate": true/false, "terms_complete": true/false, '
                '"notes": "...", "confidence": 0.0-1.0}}\n\n'
                "Submission: {submission_data}\nUnderwriting: {underwriting_result}"
            ),
            depends_on=["underwriting"],
        ),
        WorkflowStep(
            name="compliance",
            agent="openinsure-compliance",
            prompt_template=(
                "Audit this workflow for EU AI Act compliance. Check Art.12-14.\n"
                'Respond with JSON: {{"compliant": true/false, "issues": [...]}}\n\n'
                "Triage: {intake_result}\nUnderwriting: {underwriting_result}\n"
                "Policy Review: {policy_review_result}"
            ),
            depends_on=["intake", "underwriting", "policy_review"],
        ),
    ],
)

CLAIMS_WORKFLOW = WorkflowDefinition(
    name="claims_assessment",
    steps=[
        WorkflowStep(
            name="orchestration",
            agent="openinsure-orchestrator",
            prompt_template=(
                "You are coordinating a claims assessment workflow. "
                "Review the claim details and determine investigation priority.\n"
                'Respond with JSON: {{"investigation_priority": "urgent/standard/routine", '
                '"fraud_flag": false, "notes": "...", "confidence": 0.0-1.0}}\n\n'
                "Claim: {claim_data}"
            ),
            depends_on=[],
        ),
        WorkflowStep(
            name="assessment",
            agent="openinsure-claims",
            prompt_template=(
                "Assess this cyber claim. Verify coverage, estimate severity and reserve.\n"
                'Respond with JSON: {{"coverage_confirmed": true/false, '
                '"severity_tier": "simple/moderate/complex/catastrophe", '
                '"initial_reserve": N, "fraud_score": 0.0-1.0, "confidence": 0.0-1.0}}\n\n'
                "Claim: {claim_data}\nOrchestration: {orchestration_result}"
            ),
            depends_on=["orchestration"],
        ),
        WorkflowStep(
            name="compliance",
            agent="openinsure-compliance",
            prompt_template=(
                "Audit this claims assessment for EU AI Act compliance.\n"
                "Orchestration: {orchestration_result}\nAssessment: {assessment_result}"
            ),
            depends_on=["orchestration", "assessment"],
        ),
    ],
)

RENEWAL_WORKFLOW = WorkflowDefinition(
    name="renewal",
    steps=[
        WorkflowStep(
            name="assessment",
            agent="openinsure-underwriting",
            prompt_template=(
                "Assess renewal for this expiring policy. Consider claims history.\n"
                'Respond with JSON: {{"renewal_premium": N, "rate_change_pct": N, '
                '"recommendation": "renew/non_renew", "confidence": 0.0-1.0}}\n\n'
                "Policy: {policy_data}"
            ),
            depends_on=[],
        ),
        WorkflowStep(
            name="compliance",
            agent="openinsure-compliance",
            prompt_template="Audit renewal assessment.\nAssessment: {assessment_result}",
            depends_on=["assessment"],
        ),
    ],
)

# Registry — hardcoded definitions kept for backward compatibility and
# as the authoritative fallback when the data-driven registry is
# unavailable.  The ``execute_workflow`` function now queries the
# ``WorkflowRegistry`` first, falling back here.
WORKFLOWS: dict[str, WorkflowDefinition] = {
    "new_business": NEW_BUSINESS_WORKFLOW,
    "claims_assessment": CLAIMS_WORKFLOW,
    "renewal": RENEWAL_WORKFLOW,
}

# In-memory history of workflow executions
_execution_history: list[WorkflowExecution] = []
_MAX_HISTORY = 200


def get_execution_history(limit: int = 20) -> list[WorkflowExecution]:
    """Return the most recent workflow executions."""
    return list(reversed(_execution_history[-limit:]))


def get_execution_by_id(workflow_id: str) -> WorkflowExecution | None:
    """Retrieve a specific workflow execution by ID."""
    for ex in _execution_history:
        if ex.id == workflow_id:
            return ex
    return None


async def execute_workflow(
    workflow_name: str,
    entity_id: str,
    entity_type: str,
    initial_data: dict[str, Any],
    *,
    product_id: str | None = None,
) -> WorkflowExecution:
    """Execute a multi-agent workflow, running independent steps concurrently.

    When a *product_id* is provided the data-driven workflow registry is
    consulted first, allowing per-product workflow customisation.  Falls
    back to the hardcoded ``WORKFLOWS`` dict if the registry has no match.
    """
    definition: WorkflowDefinition | None = None

    # 1. Try data-driven registry when a product_id is specified
    if product_id:
        try:
            from openinsure.services.workflow_registry import get_workflow_for_product

            definition = await get_workflow_for_product(product_id, workflow_name)
        except (ValueError, Exception):
            logger.debug("workflow.registry_lookup_failed", workflow=workflow_name, exc_info=True)

    # 2. Hardcoded fallback (always used when no product_id)
    if definition is None:
        definition = WORKFLOWS.get(workflow_name)
    if not definition:
        raise ValueError(f"Unknown workflow: {workflow_name}")

    execution = WorkflowExecution(workflow_name, entity_id, entity_type)
    execution.context["entity_data"] = initial_data
    foundry = get_foundry_client()

    await publish_domain_event(
        f"workflow.{workflow_name}.started",
        f"/{entity_type}/{entity_id}",
        {"workflow_id": execution.id, "entity_id": entity_id},
    )

    completed_steps: set[str] = set()
    skipped_steps: set[str] = set()
    failed_required: bool = False

    while not failed_required:
        # Find steps whose dependencies are all satisfied
        ready: list[WorkflowStep] = []
        for step in definition.steps:
            if step.name in completed_steps or step.name in skipped_steps:
                continue
            deps_met = all(d in completed_steps or d in skipped_steps for d in step.depends_on)
            if deps_met:
                ready.append(step)

        if not ready:
            break

        # Execute ready steps concurrently via asyncio.gather
        async def _run_step(step: WorkflowStep) -> tuple[WorkflowStep, dict[str, Any] | None, str]:
            """Execute a single workflow step, returning (step, result_or_None, prompt)."""
            # Check condition
            if step.condition and not _evaluate_condition(step.condition, execution.context):
                return step, None, ""

            from openinsure.agents.prompts import build_prompt_for_step

            prompt = await build_prompt_for_step(step.name, execution.context, entity_id, entity_type)

            try:
                result = await asyncio.wait_for(foundry.invoke(step.agent, prompt), timeout=30)
                return step, result, prompt
            except TimeoutError:
                logger.warning(
                    "workflow.step_timeout",
                    workflow=workflow_name,
                    step=step.name,
                    timeout=30,
                )
                return step, {"_error": f"Step '{step.name}' timed out after 30s", "_timeout": True}, prompt
            except Exception as e:
                logger.exception(
                    "workflow.step_failed",
                    workflow=workflow_name,
                    step=step.name,
                    error=str(e),
                )
                return step, {"_error": str(e)[:200]}, prompt

        results = await asyncio.gather(*[_run_step(s) for s in ready])

        for step, result, prompt in results:
            if result is None:
                # Condition not met — skip
                execution.steps_completed.append(
                    {
                        "name": step.name,
                        "status": "skipped",
                        "reason": f"Condition not met: {step.condition}",
                    }
                )
                skipped_steps.add(step.name)
                continue

            if "_error" in result:
                step_record = {
                    "name": step.name,
                    "agent": step.agent,
                    "status": "failed",
                    "error": result["_error"],
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                execution.steps_completed.append(step_record)
                if step.required:
                    execution.status = "failed"
                    execution.error = f"Required step '{step.name}' failed: {result['_error']}"
                    failed_required = True
                    break
                skipped_steps.add(step.name)
                continue

            resp = result.get("response", {})
            confidence = resp.get("confidence", 0.8) if isinstance(resp, dict) else 0.8
            needs_human_review = confidence < 0.5

            if needs_human_review:
                logger.warning(
                    "workflow.low_confidence_flagged",
                    workflow=workflow_name,
                    step=step.name,
                    confidence=confidence,
                    entity_id=entity_id,
                )

            step_record = {
                "name": step.name,
                "agent": step.agent,
                "status": "completed",
                "source": result.get("source", "unknown"),
                "response": resp,
                "raw": str(result.get("raw", ""))[:1000],
                "confidence": confidence,
                "human_review_required": needs_human_review,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            execution.steps_completed.append(step_record)
            execution.context[f"{step.name}_result"] = resp

            if needs_human_review and step.required:
                execution.status = "escalated"
                execution.error = (
                    f"Step '{step.name}' returned low confidence ({confidence:.2f}); flagged for human review"
                )
                await publish_domain_event(
                    f"workflow.{workflow_name}.escalated",
                    f"/{entity_type}/{entity_id}",
                    {
                        "workflow_id": execution.id,
                        "step": step.name,
                        "confidence": confidence,
                        "reason": "low_confidence",
                    },
                )
                failed_required = True
                break

            # Record decision for each completed step
            try:
                from openinsure.infrastructure.factory import get_compliance_repository

                compliance_repo = get_compliance_repository()
                reasoning = str(resp.get("reasoning", "")) if isinstance(resp, dict) else str(resp)[:500]
                await compliance_repo.store_decision(
                    {
                        "decision_id": str(uuid4()),
                        "agent_id": step.agent,
                        "decision_type": step.name,
                        "entity_id": entity_id,
                        "entity_type": entity_type,
                        "confidence": float(confidence),
                        "input_summary": {
                            "entity_id": entity_id,
                            "prompt_length": len(prompt),
                            "step": step.name,
                        },
                        "output": resp if isinstance(resp, dict) else {"raw": str(resp)[:500]},
                        "reasoning": reasoning,
                        "model_used": "gpt-5.1",
                        "execution_time_ms": result.get("execution_time_ms"),
                        "human_oversight": (
                            "required" if confidence < 0.7 else "recommended" if needs_human_review else "none"
                        ),
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                )
            except Exception:
                logger.debug("decision_recording_failed", step=step.name, exc_info=True)

            await publish_domain_event(
                f"workflow.{workflow_name}.step_completed",
                f"/{entity_type}/{entity_id}",
                {
                    "workflow_id": execution.id,
                    "step": step.name,
                    "source": result.get("source"),
                },
            )
            completed_steps.add(step.name)

    if execution.status == "running":
        execution.status = "completed"
    execution.completed_at = datetime.now(UTC).isoformat()

    await publish_domain_event(
        f"workflow.{workflow_name}.{execution.status}",
        f"/{entity_type}/{entity_id}",
        {"workflow_id": execution.id, "status": execution.status},
    )

    # Store in history
    _execution_history.append(execution)
    if len(_execution_history) > _MAX_HISTORY:
        _execution_history[:] = _execution_history[-_MAX_HISTORY:]

    return execution


def _evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """Simple condition evaluator for workflow step conditions.

    Supports ``step.field == 'value'`` patterns by traversing the context
    dictionary, looking up ``<step>_result`` keys automatically.

    Returns ``False`` on any evaluation error (fail-closed) to prevent
    malformed agent responses from bypassing safety checks.
    """
    result = False
    reason = "unknown"
    try:
        parts = condition.split("==")
        if len(parts) == 2:
            path = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            keys = path.split(".")
            val: Any = context
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(f"{k}_result", val.get(k, ""))
            result = str(val).lower() == expected.lower()
            reason = "evaluated" if result else "condition_not_met"
        else:
            reason = "unparseable_condition"
    except Exception:
        logger.warning(
            "workflow.condition_eval_error",
            condition=condition,
            exc_info=True,
        )
        reason = "evaluation_error"
    logger.info(
        "workflow.condition_evaluated",
        condition=condition,
        result=result,
        reason=reason,
    )
    return result
