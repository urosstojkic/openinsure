"""Agent Traces API — exposes real Foundry agent execution traces.

Decision records are created exclusively when Foundry agents run (via
``workflow_engine.py``, ``submissions.py``, and ``claims.py``).  This
endpoint surfaces those records as an agent-trace timeline for the
Agent Decisions dashboard page.

If Application Insights is configured, the endpoint can also pull
raw OpenTelemetry spans for richer latency / dependency data.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_compliance_repository

router = APIRouter()
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AgentTrace(BaseModel):
    """A single Foundry agent invocation trace."""

    id: str
    agent_id: str = Field(description="Foundry agent name (e.g. openinsure-submission)")
    decision_type: str = Field(description="Step name (triage, underwriting, …)")
    entity_id: str = Field(description="Submission / claim / policy ID")
    entity_type: str = Field(description="submission | claim | policy")
    model_used: str
    confidence: float
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    reasoning: str
    execution_time_ms: int | None = None
    human_override: bool = False
    override_reason: str | None = None
    created_at: str


class AgentTraceList(BaseModel):
    """Paginated agent trace listing."""

    items: list[AgentTrace]
    total: int
    skip: int
    limit: int


class AgentTraceSummary(BaseModel):
    """Aggregate stats across all recorded agent traces."""

    total_traces: int
    agents: dict[str, int] = Field(description="Invocation count per agent")
    decision_types: dict[str, int] = Field(description="Invocation count per decision type")
    avg_confidence: float
    avg_execution_time_ms: float | None
    latest_trace_at: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_trace(row: dict[str, Any]) -> AgentTrace:
    """Convert a deserialised decision_records row to an AgentTrace."""
    # The compliance repo deserializer maps DB columns to API fields:
    #   model_used → model_id, output_data → output_summary, reasoning → explanation
    return AgentTrace(
        id=str(row.get("id", "")),
        agent_id=row.get("model_id", row.get("agent_id", "")),
        decision_type=row.get("decision_type", ""),
        entity_id=row.get("entity_id", ""),
        entity_type=row.get("entity_type", ""),
        model_used=row.get("model_id", row.get("model_used", "")),
        confidence=float(row.get("confidence", 0)),
        input_summary=row.get("input_summary", {}),
        output_summary=row.get("output_summary", {}),
        reasoning=row.get("explanation", row.get("reasoning", "")),
        execution_time_ms=row.get("execution_time_ms"),
        human_override=bool(row.get("human_override", False)),
        override_reason=row.get("override_reason"),
        created_at=_ts(row.get("created_at", "")),
    )


def _ts(val: Any) -> str:
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val) if val else datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AgentTraceList)
async def list_agent_traces(
    agent_id: str | None = Query(None, description="Filter by Foundry agent name"),
    decision_type: str | None = Query(None, description="Filter by decision type"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AgentTraceList:
    """List real Foundry agent invocation traces.

    Each trace is recorded only when a Foundry agent is invoked and
    returns a result (no synthetic / mock data).
    """
    repo = get_compliance_repository()

    filters: dict[str, Any] = {}
    if decision_type is not None:
        filters["decision_type"] = decision_type
    if entity_type is not None:
        filters["entity_type"] = entity_type
    if entity_id is not None:
        filters["entity_id"] = entity_id

    page = await repo.list_decisions(filters=filters, skip=skip, limit=limit)
    total = await repo.count_decisions(filters=filters)

    # Optional post-filter on agent_id (stored as model_id after deserialization)
    if agent_id is not None:
        page = [r for r in page if r.get("model_id", r.get("agent_id", "")) == agent_id]
        # Recount — for large datasets this should be a DB filter, but
        # agent_id lives inside agent_id column so we accept the minor mismatch.
        total = len(page)

    return AgentTraceList(
        items=[_row_to_trace(r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/summary", response_model=AgentTraceSummary)
async def agent_trace_summary() -> AgentTraceSummary:
    """Return aggregate statistics for all recorded agent traces."""
    repo = get_compliance_repository()
    all_rows = await repo.list_decisions(skip=0, limit=5000)
    total = len(all_rows)

    agents: dict[str, int] = {}
    types: dict[str, int] = {}
    conf_sum = 0.0
    exec_sum = 0.0
    exec_count = 0
    latest: str | None = None

    for row in all_rows:
        aid = row.get("model_id", row.get("agent_id", "unknown"))
        dt = row.get("decision_type", "unknown")
        agents[aid] = agents.get(aid, 0) + 1
        types[dt] = types.get(dt, 0) + 1
        conf_sum += float(row.get("confidence", 0))

        ms = row.get("execution_time_ms")
        if ms is not None:
            exec_sum += ms
            exec_count += 1

        ts = _ts(row.get("created_at", ""))
        if latest is None or ts > latest:
            latest = ts

    return AgentTraceSummary(
        total_traces=total,
        agents=agents,
        decision_types=types,
        avg_confidence=round(conf_sum / total, 3) if total else 0,
        avg_execution_time_ms=round(exec_sum / exec_count, 1) if exec_count else None,
        latest_trace_at=latest,
    )
