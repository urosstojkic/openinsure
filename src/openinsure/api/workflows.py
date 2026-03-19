"""Workflow orchestration API endpoints.

Provides endpoints to trigger multi-agent workflows and inspect their
execution history.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.rbac.auth import CurrentUser, get_current_user
from openinsure.services.workflow_engine import (
    execute_workflow,
    get_execution_by_id,
    get_execution_history,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class WorkflowStepResponse(BaseModel):
    """Serialisable view of a completed workflow step."""

    name: str
    agent: str = ""
    status: str = ""
    source: str = ""
    response: Any = None
    raw: str = ""
    error: str = ""
    reason: str = ""
    timestamp: str = ""


class WorkflowExecutionResponse(BaseModel):
    """Serialisable view of a workflow execution."""

    id: str
    workflow_name: str
    entity_id: str
    entity_type: str
    status: str
    steps_completed: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    completed_at: str | None = None
    error: str | None = None


class WorkflowHistoryResponse(BaseModel):
    """Paginated list of workflow executions."""

    items: list[WorkflowExecutionResponse]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _execution_to_response(ex: Any) -> WorkflowExecutionResponse:
    """Convert a WorkflowExecution object to a serialisable response."""
    return WorkflowExecutionResponse(
        id=ex.id,
        workflow_name=ex.workflow_name,
        entity_id=ex.entity_id,
        entity_type=ex.entity_type,
        status=ex.status,
        steps_completed=json.loads(json.dumps(ex.steps_completed, default=str)),
        context=json.loads(json.dumps(ex.context, default=str)),
        started_at=ex.started_at,
        completed_at=ex.completed_at,
        error=ex.error,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/new-business/{submission_id}", response_model=WorkflowExecutionResponse)
async def run_new_business_workflow(
    submission_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> WorkflowExecutionResponse:
    """Execute the new-business multi-agent workflow for a submission."""
    from openinsure.infrastructure.factory import get_submission_repository

    repo = get_submission_repository()
    submission = await repo.get_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    execution = await execute_workflow(
        "new_business",
        submission_id,
        "submission",
        submission,
    )
    return _execution_to_response(execution)


@router.post("/claims/{claim_id}", response_model=WorkflowExecutionResponse)
async def run_claims_workflow(
    claim_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> WorkflowExecutionResponse:
    """Execute the claims-assessment multi-agent workflow."""
    from openinsure.infrastructure.factory import get_claim_repository

    repo = get_claim_repository()
    claim = await repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    execution = await execute_workflow(
        "claims_assessment",
        claim_id,
        "claim",
        claim,
    )
    return _execution_to_response(execution)


@router.post("/renewal/{policy_id}", response_model=WorkflowExecutionResponse)
async def run_renewal_workflow(
    policy_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> WorkflowExecutionResponse:
    """Execute the renewal multi-agent workflow."""
    from openinsure.infrastructure.factory import get_policy_repository

    repo = get_policy_repository()
    policy = await repo.get_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    execution = await execute_workflow(
        "renewal",
        policy_id,
        "policy",
        policy,
    )
    return _execution_to_response(execution)


@router.get("/history", response_model=WorkflowHistoryResponse)
async def list_workflow_history(
    limit: int = Query(20, ge=1, le=100),
    _user: CurrentUser = Depends(get_current_user),
) -> WorkflowHistoryResponse:
    """List recent workflow executions."""
    executions = get_execution_history(limit=limit)
    items = [_execution_to_response(ex) for ex in executions]
    return WorkflowHistoryResponse(items=items, total=len(items))


@router.get("/{workflow_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    workflow_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> WorkflowExecutionResponse:
    """Get details of a specific workflow execution."""
    execution = get_execution_by_id(workflow_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")
    return _execution_to_response(execution)
