"""Automated renewal scheduling for OpenInsure.

Identifies policies approaching expiry and queues them for underwriting
review at 90/60/30-day windows. Designed for both application-level
scheduling and external triggers (Azure Logic App, cron).

Addresses issue #84.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import structlog

from openinsure.infrastructure.factory import get_policy_repository, get_renewal_repository

logger = structlog.get_logger()

# In-memory renewal queue for UW workbench
_renewal_queue: list[dict[str, Any]] = []


async def identify_and_queue_renewals() -> dict[str, Any]:
    """Daily scheduled job: identify expiring policies and queue them.

    - 90 days: create renewal record (status=pending)
    - 60 days: flag for terms generation (status=terms_due)
    - 30 days: escalate as urgent (status=urgent)
    """
    policy_repo = get_policy_repository()
    renewal_repo = get_renewal_repository()
    policies = await policy_repo.list_all(limit=5000)
    today = date.today()
    now = datetime.now(UTC).isoformat()

    existing_renewals = await renewal_repo.list_all(limit=5000)
    existing_policy_ids = {r.get("original_policy_id") for r in existing_renewals}

    stats = {"new_records": 0, "terms_due": 0, "urgent": 0, "already_queued": 0}

    for policy in policies:
        exp = policy.get("expiration_date")
        if not exp:
            continue
        try:
            exp_date = date.fromisoformat(str(exp)[:10])
        except (ValueError, TypeError):
            continue

        days_to_expiry = (exp_date - today).days
        if days_to_expiry < 0 or days_to_expiry > 90:
            continue

        policy_id = policy.get("id", "")
        policy_status = str(policy.get("status", "")).lower()
        if policy_status in ("cancelled", "expired"):
            continue

        # Determine renewal urgency
        if days_to_expiry <= 30:
            queue_status = "urgent"
            stats["urgent"] += 1
        elif days_to_expiry <= 60:
            queue_status = "terms_due"
            stats["terms_due"] += 1
        else:
            queue_status = "pending"
            stats["new_records"] += 1

        # Skip if already tracked
        if policy_id in existing_policy_ids:
            stats["already_queued"] += 1
            # Update urgency in queue
            for item in _renewal_queue:
                if item.get("policy_id") == policy_id:
                    item["status"] = queue_status
                    item["days_to_expiry"] = days_to_expiry
                    item["updated_at"] = now
            continue

        # Create renewal record
        renewal_id = str(uuid4())
        expiring_premium = float(policy.get("total_premium", policy.get("premium", 0)) or 0)

        record: dict[str, Any] = {
            "id": renewal_id,
            "original_policy_id": policy_id,
            "renewal_policy_id": None,
            "status": queue_status,
            "expiring_premium": expiring_premium,
            "renewal_premium": 0,
            "rate_change_pct": 0,
            "recommendation": "review_required",
            "conditions": [],
            "generated_by": "scheduler",
            "created_at": now,
            "updated_at": now,
        }
        await renewal_repo.create(record)
        existing_policy_ids.add(policy_id)

        # Add to UW workbench queue
        _renewal_queue.append(
            {
                "id": renewal_id,
                "policy_id": policy_id,
                "policy_number": policy.get("policy_number", ""),
                "policyholder_name": policy.get("policyholder_name", policy.get("insured_name", "")),
                "status": queue_status,
                "days_to_expiry": days_to_expiry,
                "expiring_premium": expiring_premium,
                "effective_date": str(policy.get("effective_date", "")),
                "expiration_date": str(exp),
                "badge": "Renewal",
                "recommendation": "review_required",
                "ai_terms": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    logger.info(
        "renewal_scheduler.run_complete",
        new=stats["new_records"],
        terms_due=stats["terms_due"],
        urgent=stats["urgent"],
        already_queued=stats["already_queued"],
    )
    return stats


async def get_renewal_queue(
    status: str | None = None,
    sort_by: str = "days_to_expiry",
) -> list[dict[str, Any]]:
    """Return the renewal queue for UW workbench display."""
    items = list(_renewal_queue)
    if status:
        items = [i for i in items if i.get("status") == status]
    if sort_by == "days_to_expiry":
        items.sort(key=lambda x: x.get("days_to_expiry", 999))
    elif sort_by == "premium":
        items.sort(key=lambda x: x.get("expiring_premium", 0), reverse=True)
    return items


async def pre_populate_renewal_terms(policy_id: str) -> dict[str, Any]:
    """Use the underwriting agent to pre-populate renewal terms."""
    import json

    from openinsure.agents.foundry_client import get_foundry_client

    policy_repo = get_policy_repository()
    policy = await policy_repo.get_by_id(policy_id)
    if policy is None:
        return {"error": f"Policy {policy_id} not found"}

    expiring_premium = float(policy.get("total_premium", policy.get("premium", 0)) or 0)

    foundry = get_foundry_client()
    if foundry.is_available:
        result = await foundry.invoke(
            "openinsure-underwriting",
            "Generate renewal terms for this expiring cyber policy.\n"
            "Consider claims history, market conditions, and expiring terms.\n"
            'Respond with JSON: {"renewal_premium": X, "rate_change_pct": Y, '
            '"recommendation": "renew_as_is"/"refer"/"non_renew", '
            '"conditions": [...], "confidence": 0.0-1.0}\n\n'
            f"Policy: {json.dumps(policy, default=str)[:800]}",
        )
        resp = result.get("response", {})
        if isinstance(resp, dict) and result.get("source") == "foundry":
            terms = {
                "renewal_premium": resp.get("renewal_premium", expiring_premium * 1.05),
                "rate_change_pct": resp.get("rate_change_pct", 5.0),
                "recommendation": resp.get("recommendation", "renew_as_is"),
                "conditions": resp.get("conditions", []),
                "confidence": resp.get("confidence", 0.8),
                "source": "foundry",
            }
            # Update queue item
            for item in _renewal_queue:
                if item.get("policy_id") == policy_id:
                    item["ai_terms"] = terms
                    item["recommendation"] = terms["recommendation"]
                    item["updated_at"] = datetime.now(UTC).isoformat()
            return terms

    # Fallback: simple 5% increase
    terms = {
        "renewal_premium": round(expiring_premium * 1.05, 2),
        "rate_change_pct": 5.0,
        "recommendation": "renew_as_is" if expiring_premium > 0 else "review_required",
        "conditions": [],
        "confidence": 0.5,
        "source": "system",
    }
    for item in _renewal_queue:
        if item.get("policy_id") == policy_id:
            item["ai_terms"] = terms
            item["recommendation"] = terms["recommendation"]
            item["updated_at"] = datetime.now(UTC).isoformat()
    return terms
