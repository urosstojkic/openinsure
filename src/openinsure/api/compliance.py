"""Compliance API endpoints for OpenInsure.

Provides audit-trail access, AI decision records, bias monitoring reports,
and EU AI Act system inventory endpoints.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_compliance_repository

router = APIRouter()
_logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Compliance repository — resolved by factory (in-memory or SQL)
# ---------------------------------------------------------------------------
_compliance_repo = get_compliance_repository()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DecisionType(StrEnum):
    """Types of AI-assisted decisions."""

    TRIAGE = "triage"
    UNDERWRITING = "underwriting"
    CLAIMS = "claims"
    PRICING = "pricing"
    FRAUD_DETECTION = "fraud_detection"
    POLICY_REVIEW = "policy_review"
    COMPLIANCE = "compliance"
    COMPLIANCE_AUDIT = "compliance_audit"
    ORCHESTRATION = "orchestration"
    CLAIMS_ASSESSMENT = "claims_assessment"
    RENEWAL = "renewal"
    ENRICHMENT = "enrichment"
    BILLING = "billing"
    DOCUMENT = "document"
    ANALYTICS = "analytics"
    INTAKE = "intake"
    ASSESSMENT = "assessment"


class RiskLevel(StrEnum):
    """EU AI Act risk classification."""

    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DecisionRecord(BaseModel):
    """An AI decision record for compliance transparency."""

    id: str
    decision_type: DecisionType
    entity_id: str = Field(..., description="ID of the submission, policy, or claim")
    entity_type: str = Field(..., description="submission | policy | claim")
    agent_id: str = Field("", description="Foundry agent key (e.g. openinsure-submission)")
    agent_name: str = Field("", description="Human-readable agent display name")
    model_id: str
    model_version: str
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    confidence: float
    explanation: str
    human_override: bool = False
    override_reason: str | None = None
    created_at: str


class DecisionList(BaseModel):
    """Paginated list of decision records."""

    items: list[DecisionRecord]
    total: int
    skip: int
    limit: int


class AuditEvent(BaseModel):
    """A single audit-trail event."""

    id: str
    timestamp: str
    actor: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]


class AuditTrailResponse(BaseModel):
    """Paginated audit trail."""

    items: list[AuditEvent]
    total: int
    skip: int
    limit: int


class BiasReportRequest(BaseModel):
    """Request to generate a bias monitoring report."""

    decision_type: DecisionType
    date_from: str = Field(..., description="ISO-8601 start date")
    date_to: str = Field(..., description="ISO-8601 end date")
    protected_attributes: list[str] = Field(
        default_factory=lambda: ["industry", "company_size", "geography"],
        description="Attributes to analyse for potential bias",
    )


class BiasMetric(BaseModel):
    """A single bias metric measurement."""

    attribute: str
    metric_name: str
    value: float
    threshold: float
    status: str = Field(description="'pass' or 'fail'")


class BiasReportResponse(BaseModel):
    """Generated bias monitoring report."""

    report_id: str
    decision_type: DecisionType
    date_from: str
    date_to: str
    total_decisions: int
    metrics: list[BiasMetric]
    summary: str
    generated_at: str


class AISystemEntry(BaseModel):
    """An entry in the AI system inventory (EU AI Act Art. 60)."""

    system_id: str
    name: str
    description: str
    risk_level: RiskLevel
    purpose: str
    deployer: str
    provider: str
    model_ids: list[str]
    data_sources: list[str]
    human_oversight: str
    last_assessment: str
    # Fields expected by dashboard
    version: str = ""
    status: str = "active"
    risk_category: str = "high"
    decisions_count: int = 0
    avg_confidence: float = 0.0
    id: str = ""
    last_audit: str = ""


class SystemInventoryResponse(BaseModel):
    """Full AI system inventory for EU AI Act compliance."""

    systems: list[AISystemEntry]
    total: int
    generated_at: str


class ComplianceStatsResponse(BaseModel):
    """Aggregate compliance statistics computed across ALL decisions."""

    total_decisions: int
    avg_confidence: float
    oversight_required_count: int
    oversight_recommended_count: int
    decisions_by_type: dict[str, int]
    decisions_by_agent: dict[str, int]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=ComplianceStatsResponse)
async def get_compliance_stats() -> ComplianceStatsResponse:
    """Aggregate compliance statistics computed across ALL decisions."""
    stats = await _compliance_repo.get_stats()
    return ComplianceStatsResponse(**stats)


@router.get("/decisions", response_model=DecisionList)
async def list_decisions(
    decision_type: DecisionType | None = Query(None, description="Filter by decision type"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> DecisionList:
    """List AI decision records with optional filtering."""
    filters: dict[str, Any] = {}
    if decision_type is not None:
        filters["decision_type"] = decision_type
    if entity_type is not None:
        filters["entity_type"] = entity_type
    if entity_id is not None:
        filters["entity_id"] = entity_id

    page = await _compliance_repo.list_decisions(filters=filters, skip=skip, limit=limit)
    total = await _compliance_repo.count_decisions(filters=filters)
    return DecisionList(
        items=[DecisionRecord(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/decisions/{decision_id}", response_model=DecisionRecord)
async def get_decision(decision_id: str) -> DecisionRecord:
    """Retrieve a single decision record by ID."""
    record = await _compliance_repo.get_decision(decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    return DecisionRecord(**record)


@router.get("/audit-trail", response_model=AuditTrailResponse)
async def get_audit_trail(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    actor: str | None = Query(None, description="Filter by actor"),
    action: str | None = Query(None, description="Filter by action"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AuditTrailResponse:
    """Retrieve audit trail events with optional filtering."""
    filters: dict[str, Any] = {}
    if entity_type is not None:
        filters["entity_type"] = entity_type
    if entity_id is not None:
        filters["entity_id"] = entity_id
    if actor is not None:
        filters["actor"] = actor
    if action is not None:
        filters["action"] = action

    page = await _compliance_repo.list_audit_events(filters=filters, skip=skip, limit=limit)
    total = await _compliance_repo.count_audit_events(filters=filters)
    return AuditTrailResponse(
        items=[AuditEvent(**e) for e in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/bias-report", status_code=201)
async def generate_bias_report_endpoint(
    body: BiasReportRequest | None = None,
) -> dict[str, object]:
    """Generate a bias monitoring report for AI decisions.

    Runs the real bias-monitoring engine (4/5ths rule, statistical parity)
    over all submissions, with an optional Foundry-powered overlay.
    """
    from openinsure.infrastructure.factory import get_submission_repository
    from openinsure.services.bias_monitor import generate_bias_report

    repo = get_submission_repository()
    submissions = await repo.list_all(limit=5000)
    report = await generate_bias_report(submissions)

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "audit.generated",
            "/compliance/bias-report",
            {"report_type": "bias_monitoring", "submission_count": len(submissions)},
        )
        # Emit compliance alert if bias issues were detected
        issues = report.get("issues", report.get("alerts", []))
        if issues:
            await publish_domain_event(
                "compliance.alert",
                "/compliance/bias-report",
                {"alert_type": "bias_detected", "issue_count": len(issues)},
            )
    except Exception:
        _logger.debug("event.publish_skipped", event="audit.generated")

    return report


@router.get("/system-inventory", response_model=SystemInventoryResponse)
async def get_system_inventory() -> SystemInventoryResponse:
    """Return the AI system inventory for EU AI Act compliance (Art. 60).

    Provides a registry of all AI systems deployed, their risk
    classification, purpose, and oversight arrangements.
    Decision counts and confidence are computed from real decision records.
    """
    # Fetch real decision data for per-system metrics
    all_decisions = await _compliance_repo.list_decisions(skip=0, limit=5000)

    # Map decision_type to system
    system_decision_types: dict[str, set[str]] = {
        "ai-sys-001": {"triage", "intake", "underwriting", "pricing", "orchestration"},
        "ai-sys-002": {"claims", "claims_assessment", "fraud_detection"},
        "ai-sys-003": {"pricing", "underwriting"},
    }

    system_decisions: dict[str, list[float]] = {"ai-sys-001": [], "ai-sys-002": [], "ai-sys-003": []}
    for d in all_decisions:
        dt = d.get("decision_type", "")
        conf = float(d.get("confidence", 0) or 0)
        for sys_id, types in system_decision_types.items():
            if dt in types:
                system_decisions[sys_id].append(conf)

    def _sys_stats(sys_id: str) -> tuple[int, float]:
        decs = system_decisions.get(sys_id, [])
        count = len(decs)
        avg_conf = round(sum(decs) / max(count, 1), 4) if decs else 0.0
        return count, avg_conf

    now_str = _now()
    today = now_str[:10]

    s1_count, s1_conf = _sys_stats("ai-sys-001")
    s2_count, s2_conf = _sys_stats("ai-sys-002")
    s3_count, s3_conf = _sys_stats("ai-sys-003")

    systems = [
        AISystemEntry(
            system_id="ai-sys-001",
            id="ai-sys-001",
            name="Submission Triage Agent",
            description="Automated triage and risk scoring of new insurance submissions.",
            risk_level=RiskLevel.HIGH,
            risk_category="high",
            purpose="Risk classification and routing of insurance applications.",
            deployer="OpenInsure Platform",
            provider="OpenInsure OSS",
            model_ids=["triage-agent-v1"],
            data_sources=["submission_intake", "external_risk_feeds"],
            human_oversight="Human-in-the-loop: underwriter reviews all triage decisions before binding.",
            last_assessment=now_str,
            version="2.1",
            status="active",
            decisions_count=s1_count,
            avg_confidence=s1_conf,
            last_audit=today,
        ),
        AISystemEntry(
            system_id="ai-sys-002",
            id="ai-sys-002",
            name="Claims Fraud Detection",
            description="AI model that flags potentially fraudulent claims for investigation.",
            risk_level=RiskLevel.HIGH,
            risk_category="high",
            purpose="Fraud detection and prevention in claims processing.",
            deployer="OpenInsure Platform",
            provider="OpenInsure OSS",
            model_ids=["fraud-detection-v1"],
            data_sources=["claims_data", "policy_data", "external_fraud_databases"],
            human_oversight="Human-in-the-loop: all flagged claims reviewed by claims adjuster.",
            last_assessment=now_str,
            version="1.4",
            status="active",
            decisions_count=s2_count,
            avg_confidence=s2_conf,
            last_audit=today,
        ),
        AISystemEntry(
            system_id="ai-sys-003",
            id="ai-sys-003",
            name="Rating Engine",
            description="AI-assisted premium calculation incorporating risk factors.",
            risk_level=RiskLevel.LIMITED,
            risk_category="limited",
            purpose="Premium pricing for cyber insurance products.",
            deployer="OpenInsure Platform",
            provider="OpenInsure OSS",
            model_ids=["rating-engine-v1"],
            data_sources=["product_rules", "risk_data", "market_benchmarks"],
            human_oversight="Transparency obligation: rated premiums shown with factor breakdown.",
            last_assessment=now_str,
            version="3.0",
            status="active",
            decisions_count=s3_count,
            avg_confidence=s3_conf,
            last_audit=today,
        ),
    ]

    return SystemInventoryResponse(
        systems=systems,
        total=len(systems),
        generated_at=now_str,
    )


# ---------------------------------------------------------------------------
# Decision Outcome Tracking (#179)
# ---------------------------------------------------------------------------


class DecisionOutcomeResponse(BaseModel):
    """A single decision outcome measurement."""

    id: str
    decision_id: str
    outcome_type: str
    outcome_value: float | None = None
    accuracy_score: float | None = None
    measured_at: str
    notes: str | None = None


class DecisionOutcomesListResponse(BaseModel):
    """List of outcomes for a decision."""

    decision_id: str
    items: list[DecisionOutcomeResponse] = Field(default_factory=list)
    count: int = 0


class AccuracyAgentEntry(BaseModel):
    """Per-agent accuracy breakdown."""

    agent_id: str
    outcome_type: str
    outcome_count: int
    avg_accuracy: float | None = None
    min_accuracy: float | None = None
    max_accuracy: float | None = None


class AccuracyOverall(BaseModel):
    """Overall accuracy summary."""

    total_outcomes: int = 0
    avg_accuracy: float | None = None
    decisions_measured: int = 0


class AccuracyReportResponse(BaseModel):
    """Aggregate accuracy report across all agents and outcome types."""

    generated_at: str
    overall: AccuracyOverall
    by_agent: list[AccuracyAgentEntry] = Field(default_factory=list)


@router.get("/decision-outcomes", response_model=DecisionOutcomesListResponse)
async def get_decision_outcomes(
    decision_id: str = Query(..., description="UUID of the decision record"),
) -> DecisionOutcomesListResponse:
    """Get all recorded outcomes for a specific AI decision.

    Tracks whether the decision was accurate based on real-world results
    (claims filed, renewals retained, etc.).
    """
    from openinsure.services.outcome_tracker import get_outcomes_for_decision

    outcomes = await get_outcomes_for_decision(decision_id)
    return DecisionOutcomesListResponse(
        decision_id=decision_id,
        items=[DecisionOutcomeResponse(**o) for o in outcomes],
        count=len(outcomes),
    )


@router.get("/accuracy-report", response_model=AccuracyReportResponse)
async def get_accuracy_report() -> AccuracyReportResponse:
    """Aggregate accuracy report across all agents and outcome types.

    Shows per-agent accuracy metrics and overall platform decision quality.
    This is the AI-native competitive advantage — no legacy platform can
    answer 'were our AI decisions correct?'
    """
    from openinsure.services.outcome_tracker import get_accuracy_report as _get_report

    report = await _get_report()
    return AccuracyReportResponse(
        generated_at=report["generated_at"],
        overall=AccuracyOverall(**report["overall"]),
        by_agent=[AccuracyAgentEntry(**entry) for entry in report["by_agent"]],
    )
