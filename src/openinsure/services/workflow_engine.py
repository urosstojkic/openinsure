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
    ):
        self.name = name
        self.agent = agent
        self.prompt_template = prompt_template
        self.required = required
        self.condition = condition  # e.g., "intake.appetite_match == 'yes'"


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
        ),
        WorkflowStep(
            name="compliance",
            agent="openinsure-compliance",
            prompt_template=(
                "Audit this claims assessment for EU AI Act compliance.\n"
                "Orchestration: {orchestration_result}\nAssessment: {assessment_result}"
            ),
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
        ),
        WorkflowStep(
            name="compliance",
            agent="openinsure-compliance",
            prompt_template="Audit renewal assessment.\nAssessment: {assessment_result}",
        ),
    ],
)

# Registry
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
) -> WorkflowExecution:
    """Execute a multi-agent workflow end-to-end."""
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

    for step in definition.steps:
        # Check condition
        if step.condition and not _evaluate_condition(step.condition, execution.context):
            execution.steps_completed.append(
                {
                    "name": step.name,
                    "status": "skipped",
                    "reason": f"Condition not met: {step.condition}",
                }
            )
            continue

        # Build prompt from template
        prompt = step.prompt_template
        for key, val in execution.context.items():
            prompt = prompt.replace(f"{{{key}}}", str(val)[:500])
        # Also replace specific step results
        for completed in execution.steps_completed:
            result_key = f"{completed['name']}_result"
            if result_key in prompt or f"{{{result_key}}}" in prompt:
                prompt = prompt.replace(
                    f"{{{result_key}}}",
                    str(completed.get("response", ""))[:500],
                )

        # Execute via Foundry
        try:
            result = await asyncio.wait_for(foundry.invoke(step.agent, prompt), timeout=30)
            step_record: dict[str, Any] = {
                "name": step.name,
                "agent": step.agent,
                "status": "completed",
                "source": result.get("source", "unknown"),
                "response": result.get("response", {}),
                "raw": str(result.get("raw", ""))[:1000],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            execution.steps_completed.append(step_record)
            execution.context[f"{step.name}_result"] = result.get("response", {})

            # Record decision for each completed step
            try:
                from openinsure.infrastructure.factory import get_compliance_repository

                compliance_repo = get_compliance_repository()
                resp = result.get("response", {})
                await compliance_repo.store_decision(
                    {
                        "decision_id": str(uuid4()),
                        "agent_id": step.agent,
                        "decision_type": step.name,
                        "entity_id": entity_id,
                        "entity_type": entity_type,
                        "confidence": resp.get("confidence", 0.8) if isinstance(resp, dict) else 0.8,
                        "input_summary": {"entity_id": entity_id, "prompt_preview": prompt[:300]},
                        "output": resp if isinstance(resp, dict) else {"raw": str(resp)[:500]},
                        "reasoning": str(resp.get("reasoning", "")) if isinstance(resp, dict) else "",
                        "model_used": "gpt-5.1",
                        "human_oversight": "recommended",
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
        except TimeoutError:
            logger.warning(
                "workflow.step_timeout",
                workflow=workflow_name,
                step=step.name,
                timeout=30,
            )
            step_record = {
                "name": step.name,
                "agent": step.agent,
                "status": "failed",
                "error": f"Step '{step.name}' timed out after 30s",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            execution.steps_completed.append(step_record)
            if step.required:
                execution.status = "failed"
                execution.error = f"Required step '{step.name}' timed out after 30s"
                break
        except Exception as e:
            logger.exception(
                "workflow.step_failed",
                workflow=workflow_name,
                step=step.name,
                error=str(e),
            )
            step_record = {
                "name": step.name,
                "agent": step.agent,
                "status": "failed",
                "error": str(e)[:200],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            execution.steps_completed.append(step_record)
            if step.required:
                execution.status = "failed"
                execution.error = f"Required step '{step.name}' failed: {e}"
                break

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
    """
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
            return str(val).lower() == expected.lower()
    except Exception:
        pass
    return True  # Default to true if can't evaluate
