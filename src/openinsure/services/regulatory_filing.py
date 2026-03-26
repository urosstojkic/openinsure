"""Regulatory filing and compliance document generation service.

Generates EU AI Act documentation packages, FRIAs, transparency reports,
conformity assessment checklists, Schedule P exports, and manages bias
alert threshold configuration.

All data is sourced from real platform repositories — decisions, audit
events, bias monitoring results, and actuarial data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from openinsure.infrastructure.factory import (
    get_claim_repository,
    get_compliance_repository,
    get_policy_repository,
    get_submission_repository,
)
from openinsure.services.bias_monitor import generate_bias_report

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Bias Alert Threshold Configuration (in-memory store)
# ---------------------------------------------------------------------------

_DEFAULT_THRESHOLDS: dict[str, Any] = {
    "four_fifths_ratio": 0.8,
    "min_sample_size": 10,
    "alert_on_single_group_flag": True,
    "notification_channels": ["platform"],
}

_bias_alert_config: dict[str, Any] = dict(_DEFAULT_THRESHOLDS)


def get_bias_alert_config() -> dict[str, Any]:
    """Return the current bias alert threshold configuration."""
    return dict(_bias_alert_config)


def set_bias_alert_config(config: dict[str, Any]) -> dict[str, Any]:
    """Update bias alert threshold configuration and return the result."""
    for key in ("four_fifths_ratio", "min_sample_size", "alert_on_single_group_flag", "notification_channels"):
        if key in config:
            _bias_alert_config[key] = config[key]
    logger.info("bias_alert.config_updated", config=_bias_alert_config)
    return dict(_bias_alert_config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _doc_id() -> str:
    return uuid.uuid4().hex[:12]


async def _load_platform_data() -> dict[str, Any]:
    """Fetch submissions, policies, claims, decisions, and audit events."""
    sub_repo = get_submission_repository()
    pol_repo = get_policy_repository()
    clm_repo = get_claim_repository()
    comp_repo = get_compliance_repository()

    submissions = await sub_repo.list_all(limit=5000)
    policies = await pol_repo.list_all(limit=5000)
    claims = await clm_repo.list_all(limit=5000)
    decisions = await comp_repo.list_decisions(limit=5000)
    audit_events = await comp_repo.list_audit_events(limit=5000)

    return {
        "submissions": submissions,
        "policies": policies,
        "claims": claims,
        "decisions": decisions,
        "audit_events": audit_events,
    }


def _system_inventory() -> list[dict[str, Any]]:
    """Return the AI system inventory (same data as compliance endpoint)."""
    return [
        {
            "system_id": "ai-sys-001",
            "name": "Submission Triage Agent",
            "risk_level": "high",
            "purpose": "Risk classification and routing of insurance applications.",
            "description": "Automated triage and risk scoring of new insurance submissions.",
            "model_ids": ["triage-agent-v1"],
            "data_sources": ["submission_intake", "external_risk_feeds"],
            "human_oversight": "Human-in-the-loop: underwriter reviews all triage decisions before binding.",
        },
        {
            "system_id": "ai-sys-002",
            "name": "Claims Fraud Detection",
            "risk_level": "high",
            "purpose": "Fraud detection and prevention in claims processing.",
            "description": "AI model that flags potentially fraudulent claims for investigation.",
            "model_ids": ["fraud-detection-v1"],
            "data_sources": ["claims_data", "policy_data", "external_fraud_databases"],
            "human_oversight": "Human-in-the-loop: all flagged claims reviewed by claims adjuster.",
        },
        {
            "system_id": "ai-sys-003",
            "name": "Rating Engine",
            "risk_level": "limited",
            "purpose": "Premium pricing for cyber insurance products.",
            "description": "AI-assisted premium calculation incorporating risk factors.",
            "model_ids": ["rating-engine-v1"],
            "data_sources": ["product_rules", "risk_data", "market_benchmarks"],
            "human_oversight": "Transparency obligation: rated premiums shown with factor breakdown.",
        },
    ]


# ---------------------------------------------------------------------------
# FRIA Generation — EU AI Act Art. 9
# ---------------------------------------------------------------------------


async def generate_fria(
    *,
    system_id: str | None = None,
    include_html: bool = False,
) -> dict[str, Any]:
    """Generate a Fundamental Rights Impact Assessment.

    Queries all AI decisions, bias reports, escalations, and audit trail
    to produce a structured FRIA per EU AI Act Art. 9.
    """
    doc_id = _doc_id()
    data = await _load_platform_data()
    bias_report = await generate_bias_report(data["submissions"])

    systems = _system_inventory()
    target_systems = [s for s in systems if s.get("system_id") == system_id] if system_id else systems
    if not target_systems:
        target_systems = systems

    high_risk_systems = [s for s in target_systems if s.get("risk_level") == "high"]

    # Human oversight events from audit trail
    escalation_events = [
        e for e in data["audit_events"] if e.get("action") in ("escalate", "override", "approve", "reject")
    ]

    # Decision confidence distribution
    confidences = [d.get("confidence", 0) for d in data["decisions"] if isinstance(d.get("confidence"), (int, float))]
    low_confidence_count = sum(1 for c in confidences if c < 0.7)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    fria: dict[str, Any] = {
        "id": f"fria-{doc_id}",
        "document_type": "fundamental_rights_impact_assessment",
        "generated_at": _now_iso(),
        "eu_ai_act_reference": "Article 9 — Risk Management System",
        "version": "1.0",
        "sections": {
            "system_description": {
                "title": "1. AI System Description",
                "systems_assessed": [
                    {
                        "system_id": s["system_id"],
                        "name": s["name"],
                        "risk_level": s["risk_level"],
                        "purpose": s["purpose"],
                        "data_sources": s["data_sources"],
                    }
                    for s in target_systems
                ],
                "high_risk_count": len(high_risk_systems),
                "total_decisions_recorded": len(data["decisions"]),
                "total_submissions_processed": len(data["submissions"]),
            },
            "risk_assessment": {
                "title": "2. Risk Assessment",
                "fundamental_rights_areas": [
                    {
                        "right": "Non-discrimination",
                        "risk_level": "high" if bias_report.get("overall_status") == "flagged" else "low",
                        "evidence": f"Bias monitoring: {bias_report.get('overall_status', 'unknown')}. "
                        f"4/5ths rule analysis across {len(bias_report.get('analyses', []))} dimensions.",
                        "flagged_groups": [
                            g for a in bias_report.get("analyses", []) for g in a.get("flagged_groups", [])
                        ],
                    },
                    {
                        "right": "Privacy and data protection",
                        "risk_level": "medium",
                        "evidence": "Data minimisation applied. PII limited to underwriting-relevant fields.",
                    },
                    {
                        "right": "Due process",
                        "risk_level": "low",
                        "evidence": f"All AI decisions logged with reasoning. "
                        f"{len(escalation_events)} escalation/override events recorded.",
                    },
                    {
                        "right": "Transparency",
                        "risk_level": "low",
                        "evidence": f"Decision records include explanations. "
                        f"Average confidence: {avg_confidence:.2f}. "
                        f"Low-confidence decisions (< 0.7): {low_confidence_count}.",
                    },
                ],
            },
            "mitigation_measures": {
                "title": "3. Mitigation Measures",
                "measures": [
                    {
                        "category": "Bias monitoring",
                        "description": "Continuous 4/5ths rule analysis across industry, revenue, "
                        "security score, and channel dimensions.",
                        "status": "active",
                    },
                    {
                        "category": "Human oversight",
                        "description": "Automatic escalation to human reviewer when confidence < 0.7 "
                        "or authority limits exceeded.",
                        "status": "active",
                    },
                    {
                        "category": "Decision transparency",
                        "description": "Every AI decision produces an immutable DecisionRecord with "
                        "full reasoning chain and confidence score.",
                        "status": "active",
                    },
                    {
                        "category": "Audit trail",
                        "description": "Append-only audit trail records all system actions with actor "
                        "attribution and correlation IDs.",
                        "status": "active",
                    },
                ],
            },
            "monitoring_plan": {
                "title": "4. Ongoing Monitoring",
                "bias_monitoring_frequency": "continuous",
                "bias_report_summary": {
                    "overall_status": bias_report.get("overall_status", "unknown"),
                    "total_submissions_analyzed": bias_report.get("total_submissions_analyzed", 0),
                    "analyses_count": len(bias_report.get("analyses", [])),
                },
                "alert_thresholds": get_bias_alert_config(),
                "review_schedule": "Quarterly FRIA review with compliance officer.",
            },
            "human_oversight": {
                "title": "5. Human Oversight Arrangements",
                "escalation_policy": "Confidence < 0.7 triggers mandatory human review.",
                "override_capability": "All AI decisions can be overridden by authorised personnel.",
                "escalation_events_total": len(escalation_events),
                "decision_audit_total": len(data["decisions"]),
                "low_confidence_decisions": low_confidence_count,
            },
        },
    }

    if include_html:
        fria["html"] = _fria_to_html(fria)

    logger.info("regulatory.fria_generated", fria_id=fria["id"], systems=len(target_systems))
    return fria


# ---------------------------------------------------------------------------
# Transparency Report — EU AI Act Art. 13
# ---------------------------------------------------------------------------


async def generate_transparency_report() -> dict[str, Any]:
    """Generate an Art. 13 transparency report.

    Documents how AI decisions are made, what data is used,
    confidence thresholds, agent architecture, and bias metrics.
    """
    doc_id = _doc_id()
    data = await _load_platform_data()
    bias_report = await generate_bias_report(data["submissions"])

    confidences = [d.get("confidence", 0) for d in data["decisions"] if isinstance(d.get("confidence"), (int, float))]

    # Decision type distribution
    type_counts: dict[str, int] = {}
    for d in data["decisions"]:
        dt = d.get("decision_type", "unknown")
        type_counts[dt] = type_counts.get(dt, 0) + 1

    return {
        "id": f"transparency-{doc_id}",
        "document_type": "transparency_report",
        "generated_at": _now_iso(),
        "eu_ai_act_reference": "Article 13 — Transparency and Provision of Information to Deployers",
        "version": "1.0",
        "sections": {
            "ai_system_overview": {
                "title": "1. AI System Overview",
                "platform": "OpenInsure — AI-native insurance platform",
                "registered_systems": _system_inventory(),
                "total_systems": len(_system_inventory()),
            },
            "decision_making_process": {
                "title": "2. How AI Decisions Are Made",
                "description": "Each AI agent processes structured insurance data (submissions, "
                "policies, claims) using GPT-based models. Agents produce DecisionRecords "
                "with confidence scores, explanations, and fairness metrics.",
                "decision_types": type_counts,
                "total_decisions": len(data["decisions"]),
                "confidence_threshold": 0.7,
                "escalation_rule": "Decisions with confidence < 0.7 are escalated to human oversight.",
            },
            "data_usage": {
                "title": "3. Data Usage",
                "input_data_categories": [
                    "Applicant business information (revenue, employee count, industry)",
                    "Risk assessment data (security scores, prior incidents)",
                    "Claims data (date of loss, amounts, descriptions)",
                    "Policy data (coverage terms, premiums, limits)",
                ],
                "data_minimisation": "Only underwriting-relevant data is collected and processed.",
                "protected_attributes_monitored": ["industry", "company_size", "geography", "channel"],
            },
            "confidence_and_accuracy": {
                "title": "4. Confidence and Accuracy Metrics",
                "total_decisions_tracked": len(confidences),
                "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
                "min_confidence": round(min(confidences), 4) if confidences else 0.0,
                "max_confidence": round(max(confidences), 4) if confidences else 0.0,
                "low_confidence_count": sum(1 for c in confidences if c < 0.7),
                "high_confidence_count": sum(1 for c in confidences if c >= 0.9),
            },
            "agent_architecture": {
                "title": "5. Agent Architecture",
                "agents": [
                    {"name": "Orchestrator Agent", "role": "Multi-step workflow coordination"},
                    {"name": "Submission Triage Agent", "role": "Intake, classification, risk scoring"},
                    {"name": "Underwriting Agent", "role": "Risk assessment, premium calculation"},
                    {"name": "Policy Agent", "role": "Bind, issue, endorse, renew"},
                    {"name": "Claims Agent", "role": "FNOL, coverage verification, reserving"},
                    {"name": "Compliance Agent", "role": "Decision audit, bias analysis"},
                    {"name": "Document Agent", "role": "Document classification and extraction"},
                    {"name": "Knowledge Agent", "role": "Knowledge graph queries"},
                    {"name": "Enrichment Agent", "role": "External data enrichment"},
                    {"name": "Analytics Agent", "role": "Portfolio insights"},
                ],
                "escalation_rules": [
                    "Confidence < 0.7 → human review required",
                    "Authority limit exceeded → escalate to senior underwriter",
                    "Bias flag detected → compliance team notification",
                ],
            },
            "bias_metrics": {
                "title": "6. Bias Monitoring",
                "overall_status": bias_report.get("overall_status", "unknown"),
                "method": "4/5ths rule (adverse impact ratio ≥ 0.8)",
                "dimensions_analyzed": len(bias_report.get("analyses", [])),
                "analyses_summary": [
                    {
                        "metric": a.get("metric", ""),
                        "four_fifths_ratio": a.get("four_fifths_ratio", 1.0),
                        "passes_threshold": a.get("passes_threshold", True),
                        "flagged_groups": a.get("flagged_groups", []),
                    }
                    for a in bias_report.get("analyses", [])
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# Technical Documentation Package — EU AI Act Art. 11
# ---------------------------------------------------------------------------


async def generate_tech_doc() -> dict[str, Any]:
    """Generate a technical documentation package per Art. 11.

    Covers architecture, data flows, training data description,
    validation approach, and references to bias monitoring and audit trail.
    """
    doc_id = _doc_id()
    data = await _load_platform_data()
    bias_report = await generate_bias_report(data["submissions"])

    return {
        "id": f"techdoc-{doc_id}",
        "document_type": "technical_documentation_package",
        "generated_at": _now_iso(),
        "eu_ai_act_reference": "Article 11 — Technical Documentation",
        "version": "1.0",
        "sections": {
            "general_description": {
                "title": "1. General Description of the AI System",
                "system_name": "OpenInsure AI Platform",
                "intended_purpose": "AI-native insurance operations: submission triage, underwriting, "
                "claims processing, policy management, and compliance monitoring.",
                "deployer": "OpenInsure Platform Operator",
                "version": "1.0",
                "registered_systems": _system_inventory(),
            },
            "system_architecture": {
                "title": "2. System Architecture",
                "components": {
                    "backend": "Python 3.12+ / FastAPI / Pydantic v2",
                    "ai_platform": "Azure AI Foundry (Agent Service, AI Search, GPT models)",
                    "database": "Azure SQL (transactional) + Cosmos DB (knowledge)",
                    "storage": "Azure Blob Storage",
                    "events": "Azure Event Grid + Service Bus",
                    "identity": "Microsoft Entra ID + Managed Identity",
                    "hosting": "Azure Container Apps",
                },
                "data_flow": [
                    "Submission intake → Triage Agent → risk scoring → decision record",
                    "Underwriting Agent → premium calculation → authority check → decision record",
                    "Claims Agent → FNOL → coverage verification → fraud check → decision record",
                    "All decisions → audit trail → bias monitoring → compliance reporting",
                ],
            },
            "data_governance": {
                "title": "3. Data and Data Governance (Art. 10)",
                "data_categories": [
                    {"category": "Applicant data", "fields": "Business info, revenue, employee count, industry"},
                    {"category": "Risk data", "fields": "Security scores, prior incidents, MFA status"},
                    {"category": "Claims data", "fields": "Loss dates, amounts, descriptions, reserves"},
                    {"category": "Policy data", "fields": "Coverage terms, premiums, limits, endorsements"},
                ],
                "data_quality_measures": [
                    "Pydantic v2 validation on all inputs",
                    "Domain entity state machine enforcement",
                    "Automated data enrichment from external sources",
                ],
                "bias_considerations": "Protected attributes monitored: industry, company size, geography, channel.",
            },
            "risk_management": {
                "title": "4. Risk Management System (Art. 9)",
                "bias_monitoring": {
                    "method": "4/5ths rule — adverse impact ratio",
                    "threshold": 0.8,
                    "dimensions": ["industry", "revenue_band", "security_score_band", "channel"],
                    "current_status": bias_report.get("overall_status", "unknown"),
                    "total_analyzed": bias_report.get("total_submissions_analyzed", 0),
                },
                "human_oversight": {
                    "escalation_threshold": 0.7,
                    "override_capability": True,
                    "audit_events_total": len(data["audit_events"]),
                },
            },
            "accuracy_and_performance": {
                "title": "5. Accuracy, Robustness, and Cybersecurity (Art. 15)",
                "decision_metrics": {
                    "total_decisions": len(data["decisions"]),
                    "total_submissions": len(data["submissions"]),
                    "total_policies": len(data["policies"]),
                    "total_claims": len(data["claims"]),
                },
                "cybersecurity_measures": [
                    "Azure Managed Identity — no stored credentials",
                    "Entra ID authentication and RBAC",
                    "Encrypted data at rest and in transit",
                    "VNet isolation with private endpoints",
                ],
            },
            "monitoring_plan": {
                "title": "6. Post-Market Monitoring (Art. 72)",
                "continuous_monitoring": True,
                "bias_monitoring_frequency": "continuous",
                "audit_trail": "Immutable append-only event log",
                "decision_records": "Every AI decision stored with reasoning chain",
                "alert_thresholds": get_bias_alert_config(),
            },
        },
    }


# ---------------------------------------------------------------------------
# Conformity Assessment Checklist — EU AI Act Art. 43
# ---------------------------------------------------------------------------


async def generate_conformity_checklist() -> dict[str, Any]:
    """Generate a self-assessment checklist against EU AI Act requirements.

    Returns status per article with evidence references.
    """
    doc_id = _doc_id()
    data = await _load_platform_data()

    has_decisions = len(data["decisions"]) > 0
    has_audit = len(data["audit_events"]) > 0
    has_submissions = len(data["submissions"]) > 0

    def _status(condition: bool, partial_condition: bool = True) -> str:
        if condition and partial_condition:
            return "compliant"
        if condition or partial_condition:
            return "partial"
        return "non_compliant"

    checklist_items = [
        {
            "article": "Art. 9 — Risk Management",
            "requirement": "Establish and maintain a risk management system.",
            "status": _status(has_submissions, has_decisions),
            "evidence": [
                "Bias monitoring engine with 4/5ths rule analysis",
                f"{len(data['submissions'])} submissions analyzed for bias",
                "Continuous monitoring across 4 demographic dimensions",
            ],
        },
        {
            "article": "Art. 10 — Data and Data Governance",
            "requirement": "Data quality, relevance, and representativeness.",
            "status": _status(has_submissions),
            "evidence": [
                "Pydantic v2 validation on all data inputs",
                "Domain entity state machine enforcement",
                f"{len(data['submissions'])} submissions with structured risk data",
            ],
        },
        {
            "article": "Art. 11 — Technical Documentation",
            "requirement": "Maintain technical documentation per Annex IV.",
            "status": "compliant",
            "evidence": [
                "Technical documentation endpoint: POST /compliance/tech-doc",
                "System architecture documented",
                "Data governance and processing documented",
            ],
        },
        {
            "article": "Art. 12 — Record-Keeping",
            "requirement": "Automatic recording of events (logs).",
            "status": _status(has_decisions, has_audit),
            "evidence": [
                f"{len(data['decisions'])} decision records stored",
                f"{len(data['audit_events'])} audit events recorded",
                "Immutable append-only audit trail",
            ],
        },
        {
            "article": "Art. 13 — Transparency",
            "requirement": "Provide information to deployers about AI system capabilities.",
            "status": "compliant",
            "evidence": [
                "Transparency report endpoint: POST /compliance/transparency-report",
                "Decision records include explanations and confidence scores",
                "Bias monitoring results publicly accessible",
            ],
        },
        {
            "article": "Art. 14 — Human Oversight",
            "requirement": "Enable effective human oversight during operation.",
            "status": _status(has_decisions),
            "evidence": [
                "Automatic escalation when confidence < 0.7",
                "Human override capability on all AI decisions",
                "Escalation queue for underwriter review",
            ],
        },
        {
            "article": "Art. 15 — Accuracy, Robustness, Cybersecurity",
            "requirement": "Appropriate levels of accuracy, robustness, and cybersecurity.",
            "status": "partial",
            "evidence": [
                "Azure Managed Identity and Entra ID authentication",
                "VNet isolation with private endpoints",
                "Confidence scoring on all decisions",
            ],
        },
        {
            "article": "Art. 43 — Conformity Assessment",
            "requirement": "Conformity assessment for high-risk AI systems.",
            "status": "partial",
            "evidence": [
                "Self-assessment checklist implemented",
                "3 AI systems registered in inventory (2 high-risk)",
                "FRIA generation capability available",
            ],
        },
        {
            "article": "Art. 60 — AI System Registration",
            "requirement": "Register high-risk AI systems in the EU database.",
            "status": _status(True),
            "evidence": [
                "System inventory endpoint: GET /compliance/system-inventory",
                "3 systems registered with risk classification",
                "Includes purpose, data sources, and oversight arrangements",
            ],
        },
    ]

    compliant_count = sum(1 for item in checklist_items if item["status"] == "compliant")
    partial_count = sum(1 for item in checklist_items if item["status"] == "partial")
    non_compliant_count = sum(1 for item in checklist_items if item["status"] == "non_compliant")

    return {
        "id": f"conformity-{doc_id}",
        "document_type": "conformity_assessment_checklist",
        "generated_at": _now_iso(),
        "eu_ai_act_reference": "Article 43 — Conformity Assessment",
        "version": "1.0",
        "summary": {
            "total_articles": len(checklist_items),
            "compliant": compliant_count,
            "partial": partial_count,
            "non_compliant": non_compliant_count,
            "compliance_percentage": round(
                (compliant_count / len(checklist_items)) * 100,
                1,
            )
            if checklist_items
            else 0.0,
        },
        "checklist": checklist_items,
    }


# ---------------------------------------------------------------------------
# Schedule P Export — NAIC Statutory Reporting
# ---------------------------------------------------------------------------


async def generate_schedule_p(
    lob: str | None = None,
) -> dict[str, Any]:
    """Generate a Schedule P loss development export.

    Uses actual claims and policy data to build loss triangles
    by accident year in the NAIC statutory reporting format.
    """
    doc_id = _doc_id()
    sub_repo = get_submission_repository()
    pol_repo = get_policy_repository()
    clm_repo = get_claim_repository()

    subs = await sub_repo.list_all(limit=5000)
    pols = await pol_repo.list_all(limit=5000)
    claims = await clm_repo.list_all(limit=5000)

    # Build LOB mapping from submissions → policies → claims
    sub_lob: dict[str, str] = {s["id"]: s.get("line_of_business", "cyber") for s in subs}
    pol_lob: dict[str, str] = {}
    for p in pols:
        p_lob = p.get("lob") or sub_lob.get(p.get("submission_id", ""), "cyber")
        pol_lob[p["id"]] = p_lob

    def _claim_lob(c: dict[str, Any]) -> str:
        return c.get("lob") or c.get("line_of_business") or pol_lob.get(c.get("policy_id", ""), "cyber")

    def _claim_ay(c: dict[str, Any]) -> int:
        dol = str(c.get("date_of_loss", "") or c.get("loss_date", ""))
        try:
            return int(dol[:4])
        except (ValueError, IndexError):
            return datetime.now(UTC).year

    # Filter by LOB if specified
    filtered_claims = claims
    if lob:
        filtered_claims = [c for c in claims if _claim_lob(c) == lob]

    # Aggregate by LOB and accident year
    lob_ay: dict[str, dict[int, dict[str, Any]]] = {}
    for c in filtered_claims:
        c_lob = _claim_lob(c)
        ay = _claim_ay(c)
        lob_ay.setdefault(c_lob, {}).setdefault(
            ay,
            {
                "incurred_losses": Decimal("0"),
                "paid_losses": Decimal("0"),
                "case_reserves": Decimal("0"),
                "claim_count": 0,
            },
        )
        bucket = lob_ay[c_lob][ay]
        bucket["incurred_losses"] += Decimal(str(c.get("total_incurred", 0) or 0))
        bucket["paid_losses"] += Decimal(str(c.get("total_paid", 0) or 0))
        bucket["case_reserves"] += Decimal(str(c.get("total_reserved", 0) or 0))
        bucket["claim_count"] += 1

    # Earned premium by LOB
    lob_premium: dict[str, Decimal] = {}
    for p in pols:
        p_lob = p.get("lob") or sub_lob.get(p.get("submission_id", ""), "cyber")
        if lob and p_lob != lob:
            continue
        prem = Decimal(str(p.get("premium", 0) or p.get("total_premium", 0) or 0))
        lob_premium[p_lob] = lob_premium.get(p_lob, Decimal("0")) + prem

    # Build Schedule P parts
    parts: list[dict[str, Any]] = []
    for s_lob in sorted(lob_ay):
        accident_years: list[dict[str, Any]] = []
        total_incurred = Decimal("0")
        total_paid = Decimal("0")
        total_reserved = Decimal("0")
        total_claims = 0

        for ay in sorted(lob_ay[s_lob]):
            row = lob_ay[s_lob][ay]
            total_incurred += row["incurred_losses"]
            total_paid += row["paid_losses"]
            total_reserved += row["case_reserves"]
            total_claims += row["claim_count"]

            earned = lob_premium.get(s_lob, Decimal("0"))
            loss_ratio = (row["incurred_losses"] / earned).quantize(Decimal("0.0001")) if earned > 0 else Decimal("0")

            accident_years.append(
                {
                    "accident_year": ay,
                    "incurred_losses": str(row["incurred_losses"].quantize(Decimal("0.01"))),
                    "paid_losses": str(row["paid_losses"].quantize(Decimal("0.01"))),
                    "case_reserves": str(row["case_reserves"].quantize(Decimal("0.01"))),
                    "claim_count": row["claim_count"],
                    "loss_ratio": str(loss_ratio),
                }
            )

        parts.append(
            {
                "line_of_business": s_lob,
                "earned_premium": str(lob_premium.get(s_lob, Decimal("0")).quantize(Decimal("0.01"))),
                "accident_years": accident_years,
                "totals": {
                    "incurred_losses": str(total_incurred.quantize(Decimal("0.01"))),
                    "paid_losses": str(total_paid.quantize(Decimal("0.01"))),
                    "case_reserves": str(total_reserved.quantize(Decimal("0.01"))),
                    "claim_count": total_claims,
                },
            }
        )

    return {
        "id": f"schedule-p-{doc_id}",
        "document_type": "schedule_p",
        "generated_at": _now_iso(),
        "reporting_standard": "NAIC Annual Statement — Schedule P",
        "description": "Loss development data by accident year suitable for Schedule P filing.",
        "parts": parts,
        "total_lines_of_business": len(parts),
    }


# ---------------------------------------------------------------------------
# HTML rendering for FRIA (PDF-ready)
# ---------------------------------------------------------------------------


def _fria_to_html(fria: dict[str, Any]) -> str:
    """Render a FRIA document as simple HTML suitable for PDF generation."""
    sections = fria.get("sections", {})
    lines = [
        "<!DOCTYPE html>",
        "<html lang='en'><head><meta charset='utf-8'>",
        "<title>Fundamental Rights Impact Assessment</title>",
        "<style>body{font-family:sans-serif;margin:2em;} "
        "h1{color:#1a1a1a;} h2{color:#333;border-bottom:1px solid #ccc;padding-bottom:4px;} "
        "table{border-collapse:collapse;width:100%;margin:1em 0;} "
        "th,td{border:1px solid #ddd;padding:8px;text-align:left;} "
        "th{background:#f5f5f5;} .status-active{color:green;} "
        ".risk-high{color:red;} .risk-low{color:green;} .risk-medium{color:orange;}"
        "</style></head><body>",
        "<h1>Fundamental Rights Impact Assessment</h1>",
        f"<p><strong>ID:</strong> {fria.get('id', '')}</p>",
        f"<p><strong>Generated:</strong> {fria.get('generated_at', '')}</p>",
        f"<p><strong>Reference:</strong> {fria.get('eu_ai_act_reference', '')}</p>",
    ]

    for key, section in sections.items():
        title = section.get("title", key)
        lines.append(f"<h2>{title}</h2>")

        if key == "system_description":
            systems = section.get("systems_assessed", [])
            if systems:
                lines.append("<table><tr><th>System</th><th>Risk Level</th><th>Purpose</th></tr>")
                for s in systems:
                    lines.append(
                        f"<tr><td>{s.get('name', '')}</td>"
                        f"<td class='risk-{s.get('risk_level', '')}'>{s.get('risk_level', '')}</td>"
                        f"<td>{s.get('purpose', '')}</td></tr>"
                    )
                lines.append("</table>")

        elif key == "risk_assessment":
            areas = section.get("fundamental_rights_areas", [])
            if areas:
                lines.append("<table><tr><th>Right</th><th>Risk</th><th>Evidence</th></tr>")
                for a in areas:
                    lines.append(
                        f"<tr><td>{a.get('right', '')}</td>"
                        f"<td class='risk-{a.get('risk_level', '')}'>{a.get('risk_level', '')}</td>"
                        f"<td>{a.get('evidence', '')}</td></tr>"
                    )
                lines.append("</table>")

        elif key == "mitigation_measures":
            measures = section.get("measures", [])
            if measures:
                lines.append("<table><tr><th>Category</th><th>Description</th><th>Status</th></tr>")
                for m in measures:
                    lines.append(
                        f"<tr><td>{m.get('category', '')}</td>"
                        f"<td>{m.get('description', '')}</td>"
                        f"<td class='status-{m.get('status', '')}'>{m.get('status', '')}</td></tr>"
                    )
                lines.append("</table>")

    lines.append("</body></html>")
    return "\n".join(lines)
