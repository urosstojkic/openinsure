"""Underwriter workbench API — prioritized submission queue for UW review.

Builds a ranked queue from the submissions repository, enriched with risk
scoring metadata and agent recommendations.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query

from openinsure.infrastructure.factory import get_submission_repository

router = APIRouter()


def _parse_json_field(value: Any) -> dict[str, Any]:
    """Safely parse a JSON string or return an existing dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


@router.get("/queue")
async def get_underwriter_queue(
    status: str | None = Query(None, description="Filter by submission status"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get the underwriter's submission queue.

    Returns submissions in received/triaging/underwriting/quoted statuses,
    enriched with risk score, confidence, and agent recommendation.
    """
    repo = get_submission_repository()
    all_subs = await repo.list_all(limit=500)

    uw_statuses = {"received", "triaging", "underwriting", "quoted"}
    queue = [s for s in all_subs if s.get("status") in uw_statuses]

    # Enrich each item with priority / recommendation metadata
    for item in queue:
        risk_data = _parse_json_field(item.get("risk_data"))
        triage = _parse_json_field(item.get("triage_result"))

        # Risk score: prefer triage_result, fall back to risk_data.
        # Stored as 0-1 float; UI expects 0-10 scale.
        raw_risk = triage.get("risk_score", risk_data.get("risk_score", 0))
        try:
            raw_risk = float(raw_risk)
        except (TypeError, ValueError):
            raw_risk = 0.0
        item["risk_score"] = raw_risk if raw_risk > 1 else round(raw_risk * 10, 1)

        # Confidence from triage agent result
        raw_conf = triage.get("confidence", 0.0)
        try:
            item["confidence"] = float(raw_conf)
        except (TypeError, ValueError):
            item["confidence"] = 0.0

        # Agent recommendation from triage or fallback
        item["agent_recommendation"] = (
            triage.get("recommendation") or triage.get("appetite_match") or _get_recommendation(item)
        )

        # Risk factors from triage or synthesized from risk_data
        item["risk_factors"] = triage.get("risk_factors") or _build_risk_factors(risk_data)

        # Comparable accounts — synthetic benchmarks from industry data
        item["comparable_accounts"] = _build_comparable_accounts(risk_data)

        # Recommended terms from quoted premium
        premium = item.get("quoted_premium") or 0
        try:
            premium = float(premium)
        except (TypeError, ValueError):
            premium = 0
        item["recommended_terms"] = {
            "limit": 1_000_000 if premium > 0 else 0,
            "deductible": 10_000 if premium > 0 else 0,
            "premium": premium,
            "conditions": [],
        }

        item["priority"] = _compute_priority(item)
        item["recommendation"] = item.get("agent_recommendation") or _get_recommendation(item)
        item["due_date"] = ""  # SLA-based — populated by workflow engine

    # Sort: urgent first, then by created_at ascending
    queue.sort(
        key=lambda x: (
            {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("priority", "medium"), 2),
            x.get("created_at", ""),
        )
    )

    if status:
        queue = [q for q in queue if q.get("status") == status]

    return {"items": queue[:limit], "total": len(queue)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_HIGH_RISK_INDUSTRIES = frozenset({"healthcare", "financial_services", "retail", "energy"})


def _build_risk_factors(risk_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Synthesize risk factor breakdown from available risk_data fields."""
    factors: list[dict[str, Any]] = []

    security = risk_data.get("security_score")
    if security is not None:
        try:
            s = float(security)
        except (TypeError, ValueError):
            s = 0
        score = round(s * 100) if s <= 1 else round(s)
        factors.append(
            {
                "factor": "Security Posture",
                "impact": "positive" if score >= 70 else ("negative" if score < 50 else "neutral"),
                "score": score,
                "description": f"Security maturity score: {score}/100",
            }
        )

    industry = risk_data.get("industry", "")
    if industry:
        score = 40 if industry in _HIGH_RISK_INDUSTRIES else 70
        factors.append(
            {
                "factor": "Industry Risk",
                "impact": "negative" if industry in _HIGH_RISK_INDUSTRIES else "positive",
                "score": score,
                "description": f"{industry.replace('_', ' ').title()} sector risk profile",
            }
        )

    revenue = risk_data.get("annual_revenue", 0)
    if revenue:
        try:
            rev = float(revenue)
        except (TypeError, ValueError):
            rev = 0
        score = 80 if rev < 5_000_000 else (60 if rev < 25_000_000 else 40)
        factors.append(
            {
                "factor": "Revenue Exposure",
                "impact": "positive" if score >= 70 else ("negative" if score < 50 else "neutral"),
                "score": score,
                "description": f"Annual revenue: ${rev:,.0f}",
            }
        )

    employees = risk_data.get("employee_count", 0)
    if employees:
        try:
            emp = int(employees)
        except (TypeError, ValueError):
            emp = 0
        score = 75 if emp < 100 else (55 if emp < 500 else 35)
        factors.append(
            {
                "factor": "Organization Size",
                "impact": "positive" if score >= 70 else ("negative" if score < 50 else "neutral"),
                "score": score,
                "description": f"{emp:,} employees",
            }
        )

    return factors


def _build_comparable_accounts(risk_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return synthetic comparable-accounts benchmarks for the detail panel."""
    industry = risk_data.get("industry", "")
    if not industry:
        return []

    # Benchmarks keyed by industry — representative peer data
    _benchmarks: dict[str, list[dict[str, Any]]] = {
        "technology": [
            {
                "company": "TechSecure Inc",
                "industry": "Technology",
                "premium": 18_500,
                "limit": 1_000_000,
                "loss_ratio": 0.45,
            },
            {
                "company": "CloudGuard SaaS",
                "industry": "Technology",
                "premium": 24_000,
                "limit": 2_000_000,
                "loss_ratio": 0.38,
            },
        ],
        "healthcare": [
            {
                "company": "MedShield Corp",
                "industry": "Healthcare",
                "premium": 32_000,
                "limit": 2_000_000,
                "loss_ratio": 0.52,
            },
            {
                "company": "HealthFirst IT",
                "industry": "Healthcare",
                "premium": 21_000,
                "limit": 1_000_000,
                "loss_ratio": 0.48,
            },
        ],
        "financial_services": [
            {
                "company": "FinSecure Partners",
                "industry": "Financial Services",
                "premium": 45_000,
                "limit": 5_000_000,
                "loss_ratio": 0.35,
            },
            {
                "company": "BankShield Ltd",
                "industry": "Financial Services",
                "premium": 38_000,
                "limit": 2_000_000,
                "loss_ratio": 0.42,
            },
        ],
    }
    default = [
        {
            "company": "Industry Peer A",
            "industry": industry.replace("_", " ").title(),
            "premium": 20_000,
            "limit": 1_000_000,
            "loss_ratio": 0.44,
        },
        {
            "company": "Industry Peer B",
            "industry": industry.replace("_", " ").title(),
            "premium": 28_000,
            "limit": 2_000_000,
            "loss_ratio": 0.40,
        },
    ]
    return _benchmarks.get(industry, default)


def _compute_priority(sub: dict[str, Any]) -> str:
    """Compute priority from risk data and status."""
    risk = sub.get("risk_score", 0)
    status = sub.get("status", "")
    if status == "quoted":
        return "high"  # needs binding decision
    if risk > 7:
        return "urgent"
    if risk > 5:
        return "high"
    return "medium"


def _get_recommendation(sub: dict[str, Any]) -> str:
    """Generate recommendation text based on submission status."""
    recs = {
        "received": "Pending triage",
        "triaging": "In triage — awaiting risk assessment",
        "underwriting": "Under review — pricing in progress",
        "quoted": "Quote issued — awaiting bind decision",
    }
    return recs.get(sub.get("status", ""), "Review required")
