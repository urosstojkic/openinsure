"""Real-time operational metrics for OpenInsure dashboards.

Computes KPIs from Azure SQL data for CEO, CUO, and operations views.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import (
    get_claim_repository,
    get_compliance_repository,
    get_policy_repository,
    get_submission_repository,
)
from openinsure.infrastructure.repository import fetch_all_pages

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers — shared premium / processing-time logic
# ---------------------------------------------------------------------------


def _policy_premium(p: dict[str, Any]) -> float:
    """Extract written premium from a policy dict."""
    return float(p.get("written_premium") or p.get("premium") or p.get("total_premium") or 0)


def _earned_premium(p: dict[str, Any], as_of: date) -> float:
    """Compute the pro-rata earned portion of a policy's premium."""
    prem = _policy_premium(p)
    try:
        eff = date.fromisoformat(str(p.get("effective_date", ""))[:10])
        exp = date.fromisoformat(str(p.get("expiration_date", ""))[:10])
        term_days = max((exp - eff).days, 1)
        elapsed = min(max((as_of - eff).days, 0), term_days)
        return prem * (elapsed / term_days)
    except (ValueError, TypeError):
        return prem


def _parse_ts(val: Any) -> datetime | None:
    """Parse a timestamp value from the database into a datetime."""
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _avg_processing_hours(submissions: list[dict[str, Any]]) -> float:
    """Compute AVG(triaged_at - received_at) in hours from submissions."""
    hours: list[float] = []
    for s in submissions:
        t0 = _parse_ts(s.get("triaged_at") or s.get("received_at"))
        t1_field = s.get("triaged_at") or s.get("updated_at")
        t1 = _parse_ts(t1_field)
        t0_field = s.get("received_at") or s.get("created_at")
        t0 = _parse_ts(t0_field)
        if t0 and t1 and t1 > t0:
            diff_h = (t1 - t0).total_seconds() / 3600
            if diff_h > 0:
                hours.append(diff_h)
    return round(sum(hours) / len(hours), 1) if hours else 0.0


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class StatusCounts(BaseModel):
    """Counts keyed by status string."""

    model_config = {"extra": "allow"}


class SubmissionMetrics(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    bind_rate: float = 0.0
    decline_rate: float = 0.0


class PolicyMetrics(BaseModel):
    total: int
    active: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    total_premium: float = 0.0
    avg_premium: float = 0.0


class ClaimMetrics(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    total_incurred: float = 0.0
    loss_ratio: float = 0.0


class KPIMetrics(BaseModel):
    gwp: float = 0.0
    loss_ratio: float = 0.0
    bind_rate: float = 0.0
    active_policies: int = 0
    open_claims: int = 0
    pending_escalations: int = 0
    avg_processing_time_hours: float = 0.0


class SummaryMetricsResponse(BaseModel):
    submissions: SubmissionMetrics
    policies: PolicyMetrics
    claims: ClaimMetrics
    kpis: KPIMetrics


class PipelineMetricsResponse(BaseModel):
    pipeline: dict[str, int]
    total: int


class AgentMetricsResponse(BaseModel):
    agent_activity: dict[str, int] = Field(default_factory=dict)
    total_events: int = 0


class AgentStatusItem(BaseModel):
    """Status of an individual AI agent derived from real decision records."""

    name: str = Field(description="Internal agent key")
    display_name: str = Field(description="Human-readable agent name")
    status: Literal["active", "idle", "error"] = "idle"
    last_action: str = ""
    decisions_today: int = 0
    total_decisions: int = 0


class AgentStatusResponse(BaseModel):
    """Aggregated agent status for the dashboard Agent Status tile."""

    agents: list[AgentStatusItem] = Field(default_factory=list)
    total_decisions: int = 0
    decisions_today: int = 0


class PremiumTrendItem(BaseModel):
    month: str
    premium: float


class PremiumTrendResponse(BaseModel):
    trend: list[PremiumTrendItem] = Field(default_factory=list)


class ExecutiveKPIs(BaseModel):
    gwp: float
    nwp: float
    loss_ratio: float
    combined_ratio: float
    growth_rate: float


class LossRatioByLOB(BaseModel):
    lob: str
    loss_ratio: float


class ExposureConcentration(BaseModel):
    name: str
    exposure: float


class PipelineStage(BaseModel):
    stage: str
    count: int


class AgentImpact(BaseModel):
    processing_time_reduction: int = 0
    auto_bind_rate: float = 0.0
    escalation_rate: float = 0.0


class ExecutiveDashboardResponse(BaseModel):
    kpis: ExecutiveKPIs
    premium_trend: list[PremiumTrendItem] = Field(default_factory=list)
    loss_ratio_by_lob: list[LossRatioByLOB] = Field(default_factory=list)
    exposure_concentrations: list[ExposureConcentration] = Field(default_factory=list)
    pipeline: list[PipelineStage] = Field(default_factory=list)
    agent_impact: AgentImpact = Field(default_factory=AgentImpact)


@router.get(
    "/summary",
    response_model=SummaryMetricsResponse,
    summary="Summary KPIs",
    description="Top-level key performance indicators for the executive dashboard: "
    "submissions, policies, claims, premiums, loss ratios.",
)
async def get_summary_metrics() -> dict[str, Any]:
    """Top-level KPIs for the main dashboard."""
    from openinsure.services.escalation import count_pending

    sub_repo = get_submission_repository()
    pol_repo = get_policy_repository()
    clm_repo = get_claim_repository()

    total_subs = await sub_repo.count()
    total_pols = await pol_repo.count()
    total_claims = await clm_repo.count()

    # Fetch ALL records (paging past the 1000-row safety cap)
    subs = await fetch_all_pages(sub_repo)
    pols = await fetch_all_pages(pol_repo)
    claims = await fetch_all_pages(clm_repo)

    # Count submissions by status
    status_counts: dict[str, int] = {}
    for s in subs:
        st = s.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    # Policies by status and premium
    pol_status: dict[str, int] = {}
    total_premium = 0.0
    today = datetime.now(UTC).date()
    earned_premium_total = 0.0
    for p in pols:
        st = p.get("status", "unknown")
        pol_status[st] = pol_status.get(st, 0) + 1
        total_premium += _policy_premium(p)
        earned_premium_total += _earned_premium(p, today)

    active_pols = pol_status.get("active", 0)

    # Claims by status and total incurred
    claim_status: dict[str, int] = {}
    total_incurred = 0.0
    for c in claims:
        st = c.get("status", "unknown")
        claim_status[st] = claim_status.get(st, 0) + 1
        total_incurred += float(c.get("total_incurred", 0) or 0)

    # Loss ratio = total_incurred / earned_premium (NOT GWP)
    loss_ratio = round(total_incurred / earned_premium_total * 100, 1) if earned_premium_total > 0 else 0
    bind_rate = round(status_counts.get("bound", 0) / total_subs * 100, 1) if total_subs > 0 else 0
    decline_rate = round(status_counts.get("declined", 0) / total_subs * 100, 1) if total_subs > 0 else 0

    # Processing time from submission stage timestamps
    avg_proc_hours = _avg_processing_hours(subs)

    # Count decisions needing oversight
    comp_repo = get_compliance_repository()
    comp_stats = await comp_repo.get_stats()
    oversight_recommended = comp_stats.get("oversight_recommended_count", 0)

    return {
        "submissions": {
            "total": total_subs,
            "by_status": status_counts,
            "bind_rate": bind_rate,
            "decline_rate": decline_rate,
        },
        "policies": {
            "total": total_pols,
            "active": active_pols,
            "by_status": pol_status,
            "total_premium": round(total_premium, 2),
            "avg_premium": round(total_premium / total_pols, 2) if total_pols > 0 else 0,
        },
        "claims": {
            "total": total_claims,
            "by_status": claim_status,
            "total_incurred": round(total_incurred, 2),
            "loss_ratio": loss_ratio,
        },
        "kpis": {
            "gwp": round(total_premium, 2),
            "loss_ratio": loss_ratio,
            "bind_rate": bind_rate,
            "active_policies": active_pols,
            "open_claims": total_claims
            - claim_status.get("closed", 0)
            - claim_status.get("denied", 0)
            - claim_status.get("settled", 0),
            "pending_escalations": await count_pending(),
            "pending_decisions": oversight_recommended,
            "avg_processing_time_hours": avg_proc_hours,
        },
    }


@router.get("/pipeline", response_model=PipelineMetricsResponse)
async def get_pipeline_metrics() -> dict[str, Any]:
    """Submission pipeline funnel."""
    repo = get_submission_repository()
    subs = await fetch_all_pages(repo)
    pipeline: dict[str, int] = {}
    for s in subs:
        st = s.get("status", "unknown")
        pipeline[st] = pipeline.get(st, 0) + 1
    return {"pipeline": pipeline, "total": len(subs)}


@router.get("/agents", response_model=AgentMetricsResponse)
async def get_agent_metrics() -> dict[str, Any]:
    """Agent performance metrics (from decision records)."""
    from openinsure.services.event_publisher import get_recent_events

    events = get_recent_events(100)

    agent_events: dict[str, int] = {}
    for e in events:
        etype = e.get("event_type", "")
        if "." in etype:
            parts = etype.split(".")
            agent = parts[0] if parts[0] != "workflow" else parts[1] if len(parts) > 1 else "unknown"
            agent_events[agent] = agent_events.get(agent, 0) + 1

    return {
        "agent_activity": agent_events,
        "total_events": len(events),
    }


@router.get("/agent-status", response_model=AgentStatusResponse)
async def get_agent_status() -> AgentStatusResponse:
    """Real-time agent status derived from decision_records.

    Returns per-agent activity stats (decisions today, last action,
    active/idle status) for the dashboard Agent Status tile.
    All 10 Foundry agents are always included even if they have no decisions.
    """
    from datetime import datetime

    # Canonical list of all 10 Foundry agents
    foundry_agents: dict[str, str] = {
        "openinsure-orchestrator": "Orchestrator Agent",
        "openinsure-submission": "Submission Intake Agent",
        "openinsure-underwriting": "Underwriting Agent",
        "openinsure-policy": "Policy Management Agent",
        "openinsure-claims": "Claims Assessment Agent",
        "openinsure-compliance": "Compliance Agent",
        "openinsure-billing": "Billing Agent",
        "openinsure-document": "Document Agent",
        "openinsure-analytics": "Analytics Agent",
        "openinsure-enrichment": "Enrichment Agent",
    }

    repo = get_compliance_repository()
    all_rows = await repo.list_decisions(skip=0, limit=5000)

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    # Accumulate per-agent stats
    agent_totals: dict[str, int] = {}
    agent_today: dict[str, int] = {}
    agent_last_ts: dict[str, str] = {}
    agent_last_action: dict[str, str] = {}
    agent_display: dict[str, str] = {}

    for row in all_rows:
        raw_aid = row.get("agent_id", row.get("model_id", "unknown"))
        # Normalise to canonical agent key when possible
        aid = raw_aid
        for key in foundry_agents:
            if key in str(raw_aid).lower() or raw_aid.lower().replace(" ", "-") == key:
                aid = key
                break

        display = (
            foundry_agents.get(aid, "") or row.get("agent_name", "") or aid.replace("-", " ").replace("_", " ").title()
        )
        decision_type = row.get("decision_type", "")

        agent_totals[aid] = agent_totals.get(aid, 0) + 1
        agent_display[aid] = display

        ts_raw = row.get("created_at", "")
        ts = ts_raw.isoformat() if hasattr(ts_raw, "isoformat") else str(ts_raw)

        if ts[:10] == today:
            agent_today[aid] = agent_today.get(aid, 0) + 1

        if aid not in agent_last_ts or ts > agent_last_ts[aid]:
            agent_last_ts[aid] = ts
            entity_id = str(row.get("entity_id", ""))[:12]
            agent_last_action[aid] = (
                f"{decision_type.replace('_', ' ').capitalize()} — {entity_id}"
                if entity_id
                else decision_type.replace("_", " ").capitalize()
            )

    # Build response: start with agents that have decisions, then add remaining
    agents: list[AgentStatusItem] = []
    seen: set[str] = set()

    for aid in sorted(agent_totals, key=lambda k: agent_totals[k], reverse=True):
        today_count = agent_today.get(aid, 0)
        agents.append(
            AgentStatusItem(
                name=aid,
                display_name=agent_display.get(aid, aid),
                status="active" if today_count > 0 else "idle",
                last_action=agent_last_action.get(aid, "Ready"),
                decisions_today=today_count,
                total_decisions=agent_totals[aid],
            )
        )
        seen.add(aid)

    # Ensure all 10 canonical agents appear
    for aid, display in foundry_agents.items():
        if aid not in seen:
            agents.append(
                AgentStatusItem(
                    name=aid,
                    display_name=display,
                    status="idle",
                    last_action="Ready",
                    decisions_today=0,
                    total_decisions=0,
                )
            )

    return AgentStatusResponse(
        agents=agents,
        total_decisions=len(all_rows),
        decisions_today=sum(agent_today.values()),
    )


async def get_premium_trend() -> dict[str, Any]:
    """Monthly premium trend from policies."""
    repo = get_policy_repository()
    pols = await fetch_all_pages(repo)

    monthly: dict[str, float] = {}
    for p in pols:
        eff = str(p.get("effective_date", ""))[:7]  # "2025-06"
        if eff:
            premium = _policy_premium(p)
            monthly[eff] = monthly.get(eff, 0) + premium

    # Sort by month
    trend = [{"month": k, "premium": round(v, 2)} for k, v in sorted(monthly.items())]
    return {"trend": trend}


@router.get("/executive", response_model=ExecutiveDashboardResponse)
async def get_executive_dashboard() -> dict[str, Any]:
    """Aggregated executive KPIs for CEO / CUO / CFO dashboards.

    Returns the shape expected by the React ``ExecutiveDashboardData`` type:
    kpis (gwp, nwp, loss_ratio, combined_ratio, growth_rate as decimals),
    premium_trend, loss_ratio_by_lob, exposure_concentrations,
    pipeline (array of {stage, count}), and agent_impact.
    """
    summary = await get_summary_metrics()
    pipeline_raw = await get_pipeline_metrics()
    trend = await get_premium_trend()

    gwp = summary["policies"]["total_premium"]

    # Use earned premium for loss ratio (not GWP)
    pol_repo = get_policy_repository()
    clm_repo = get_claim_repository()
    sub_repo = get_submission_repository()

    pols = await fetch_all_pages(pol_repo)
    claims = await fetch_all_pages(clm_repo)
    subs = await fetch_all_pages(sub_repo)

    today = datetime.now(UTC).date()
    earned_prem = sum(_earned_premium(p, today) for p in pols)
    total_incurred = sum(float(c.get("total_incurred", 0) or 0) for c in claims)
    loss_ratio = total_incurred / earned_prem if earned_prem > 0 else 0
    expense_ratio = 0.34
    combined_ratio = min(loss_ratio + expense_ratio, 1.5)

    # NWP approximation: GWP minus ceded premium (default 15% cession)
    nwp = gwp * 0.85

    # Compute growth rate from year-over-year premium change
    now = datetime.now(UTC)
    this_year_prem = 0.0
    last_year_prem = 0.0
    for p in pols:
        eff = str(p.get("effective_date", ""))[:4]
        prem = _policy_premium(p)
        if eff == str(now.year):
            this_year_prem += prem
        elif eff == str(now.year - 1):
            last_year_prem += prem
    growth_rate = (this_year_prem - last_year_prem) / last_year_prem if last_year_prem > 0 else 0.0

    # --- Loss ratio by LOB ---------------------------------------------------
    # Prefer submission line_of_business (most accurate); fall back to policy lob
    sub_lob = {s.get("id"): s.get("line_of_business", "") for s in subs}
    pol_lob: dict[str, str] = {}
    pol_premium: dict[str, float] = {}
    for p in pols:
        lob = sub_lob.get(p.get("submission_id"), "") or p.get("lob") or "cyber"
        pol_lob[p["id"]] = lob
        pol_premium.setdefault(lob, 0)
        pol_premium[lob] += _policy_premium(p)

    lob_incurred: dict[str, float] = {}
    for c in claims:
        lob = pol_lob.get(c.get("policy_id", ""), "cyber")
        lob_incurred.setdefault(lob, 0)
        lob_incurred[lob] += float(c.get("total_incurred", 0) or 0)

    loss_ratio_by_lob = []
    for lob in sorted(set(list(pol_premium.keys()) + list(lob_incurred.keys()))):
        prem = pol_premium.get(lob, 0)
        inc = lob_incurred.get(lob, 0)
        lr = inc / prem if prem > 0 else 0
        display_name = lob.replace("_", " ").title()
        loss_ratio_by_lob.append({"lob": display_name, "loss_ratio": round(lr, 4)})

    # --- Exposure concentrations (by policyholder) ----------------------------
    exposure_concentrations = sorted(
        [
            {
                "name": p.get("policyholder_name") or p.get("insured_name") or "Unknown",
                "exposure": _policy_premium(p),
            }
            for p in pols
            if _policy_premium(p) > 0
        ],
        key=lambda x: x["exposure"],
        reverse=True,
    )[:10]

    # --- Pipeline as array of {stage, count} ----------------------------------
    pipeline_array = [
        {"stage": stage.capitalize(), "count": count} for stage, count in pipeline_raw["pipeline"].items()
    ]

    # --- Agent impact — processing time from submission timestamps ------------
    avg_proc = _avg_processing_hours(subs)
    proc_reduction = round((1 - avg_proc / 72) * 100) if avg_proc > 0 else 0

    return {
        "kpis": {
            "gwp": round(gwp, 2),
            "nwp": round(nwp, 2),
            "loss_ratio": round(loss_ratio, 4),
            "combined_ratio": round(combined_ratio, 4),
            "growth_rate": round(growth_rate, 4),
        },
        "premium_trend": trend["trend"],
        "loss_ratio_by_lob": loss_ratio_by_lob,
        "exposure_concentrations": exposure_concentrations,
        "pipeline": pipeline_array,
        "agent_impact": {
            "processing_time_reduction": proc_reduction,
            "auto_bind_rate": summary["submissions"].get("bind_rate", 0),
            "escalation_rate": round(
                summary["kpis"].get("pending_escalations", 0) / max(summary["submissions"]["total"], 1) * 100,
                1,
            ),
        },
    }
