"""Underwriter workbench API — prioritized submission queue for UW review.

Builds a ranked queue from the submissions repository, enriched with risk
scoring metadata and agent recommendations.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from openinsure.infrastructure.factory import get_submission_repository

router = APIRouter()


@router.get("/queue")
async def get_underwriter_queue(
    status: str | None = Query(None, description="Filter by submission status"),
    limit: int = Query(20, ge=1, le=100),
):
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
        risk_data = item.get("risk_data", {})
        if isinstance(risk_data, str):
            try:
                risk_data = json.loads(risk_data)
            except (json.JSONDecodeError, TypeError):
                risk_data = {}
        item["risk_score"] = risk_data.get("risk_score", 0)
        item["confidence"] = 0.0  # Will be set by agent when processed
        item["priority"] = _compute_priority(item)
        item["recommendation"] = _get_recommendation(item)
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


def _compute_priority(sub: dict) -> str:
    """Compute priority from risk data and status."""
    risk = sub.get("risk_score", 0)
    status = sub.get("status", "")
    if status == "quoted":
        return "high"  # needs binding decision
    if risk > 70:
        return "urgent"
    if risk > 50:
        return "high"
    return "medium"


def _get_recommendation(sub: dict) -> str:
    """Generate recommendation text based on submission status."""
    recs = {
        "received": "Pending triage",
        "triaging": "In triage — awaiting risk assessment",
        "underwriting": "Under review — pricing in progress",
        "quoted": "Quote issued — awaiting bind decision",
    }
    return recs.get(sub.get("status", ""), "Review required")
