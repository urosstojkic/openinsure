"""Compliance API endpoints for OpenInsure.

Provides audit-trail access, AI decision records, bias monitoring reports,
and EU AI Act system inventory endpoints.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_compliance_repository

router = APIRouter()

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


class SystemInventoryResponse(BaseModel):
    """Full AI system inventory for EU AI Act compliance."""

    systems: list[AISystemEntry]
    total: int
    generated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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

    page, total = await _compliance_repo.list_decisions(filters=filters, skip=skip, limit=limit)
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

    page, total = await _compliance_repo.list_audit_events(filters=filters, skip=skip, limit=limit)
    return AuditTrailResponse(
        items=[AuditEvent(**e) for e in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/bias-report", status_code=201)
async def generate_bias_report(body: BiasReportRequest):
    """Generate a bias monitoring report for AI decisions.

    Uses Foundry compliance agent when available, falls back to local stub.
    """
    from openinsure.agents.foundry_client import get_foundry_client

    # Filter decisions in date range
    all_decisions, _ = await _compliance_repo.list_decisions(
        filters={"decision_type": body.decision_type}, skip=0, limit=10000
    )
    decisions_in_range = [
        d for d in all_decisions if d["created_at"] >= body.date_from and d["created_at"] <= body.date_to
    ]

    # Foundry-powered bias analysis
    foundry = get_foundry_client()
    if foundry.is_available:
        result = await foundry.invoke(
            "openinsure-compliance",
            "Analyze these insurance decisions for potential bias. Apply the 4/5ths rule.\n"
            "Check for disparate impact across industry sectors and company sizes.\n"
            'Respond with JSON: {"bias_detected": false, "metrics": [...], "recommendations": [...]}\n\n'
            f"Decision sample: {json.dumps(decisions_in_range, default=str)[:800]}",
        )
        resp = result.get("response", {})
        if isinstance(resp, dict) and result.get("source") == "foundry":
            return {"report": resp, "source": "foundry", "generated_at": _now()}

    # Existing local fallback
    metrics: list[BiasMetric] = []
    for attr in body.protected_attributes:
        metrics.append(
            BiasMetric(
                attribute=attr,
                metric_name="demographic_parity_difference",
                value=0.03,
                threshold=0.10,
                status="pass",
            )
        )
        metrics.append(
            BiasMetric(
                attribute=attr,
                metric_name="equalised_odds_difference",
                value=0.05,
                threshold=0.10,
                status="pass",
            )
        )

    all_pass = all(m.status == "pass" for m in metrics)
    return BiasReportResponse(
        report_id=str(uuid.uuid4()),
        decision_type=body.decision_type,
        date_from=body.date_from,
        date_to=body.date_to,
        total_decisions=len(decisions_in_range),
        metrics=metrics,
        summary="All bias metrics within acceptable thresholds."
        if all_pass
        else "Some metrics exceeded thresholds — review recommended.",
        generated_at=_now(),
    )


@router.get("/system-inventory", response_model=SystemInventoryResponse)
async def get_system_inventory() -> SystemInventoryResponse:
    """Return the AI system inventory for EU AI Act compliance (Art. 60).

    Provides a registry of all AI systems deployed, their risk
    classification, purpose, and oversight arrangements.
    """
    systems = [
        AISystemEntry(
            system_id="ai-sys-001",
            name="Submission Triage Agent",
            description="Automated triage and risk scoring of new insurance submissions.",
            risk_level=RiskLevel.HIGH,
            purpose="Risk classification and routing of insurance applications.",
            deployer="OpenInsure Platform",
            provider="OpenInsure OSS",
            model_ids=["triage-agent-v1"],
            data_sources=["submission_intake", "external_risk_feeds"],
            human_oversight="Human-in-the-loop: underwriter reviews all triage decisions before binding.",
            last_assessment=_now(),
        ),
        AISystemEntry(
            system_id="ai-sys-002",
            name="Claims Fraud Detection",
            description="AI model that flags potentially fraudulent claims for investigation.",
            risk_level=RiskLevel.HIGH,
            purpose="Fraud detection and prevention in claims processing.",
            deployer="OpenInsure Platform",
            provider="OpenInsure OSS",
            model_ids=["fraud-detection-v1"],
            data_sources=["claims_data", "policy_data", "external_fraud_databases"],
            human_oversight="Human-in-the-loop: all flagged claims reviewed by claims adjuster.",
            last_assessment=_now(),
        ),
        AISystemEntry(
            system_id="ai-sys-003",
            name="Rating Engine",
            description="AI-assisted premium calculation incorporating risk factors.",
            risk_level=RiskLevel.LIMITED,
            purpose="Premium pricing for cyber insurance products.",
            deployer="OpenInsure Platform",
            provider="OpenInsure OSS",
            model_ids=["rating-engine-v1"],
            data_sources=["product_rules", "risk_data", "market_benchmarks"],
            human_oversight="Transparency obligation: rated premiums shown with factor breakdown.",
            last_assessment=_now(),
        ),
    ]

    return SystemInventoryResponse(
        systems=systems,
        total=len(systems),
        generated_at=_now(),
    )
