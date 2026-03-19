"""Escalation queue for decisions exceeding agent authority.

When an agent action exceeds the current user's authority, the action
is queued for approval by someone with sufficient authority.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()

# In-memory escalation queue (replace with SQL table in production)
_escalation_queue: list[dict[str, Any]] = []


async def escalate(
    action: str,
    entity_type: str,
    entity_id: str,
    requested_by: str,
    requested_role: str,
    amount: float,
    authority_result: dict,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add an item to the escalation queue."""
    item = {
        "id": str(uuid4()),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "requested_by": requested_by,
        "requested_role": requested_role,
        "amount": amount,
        "required_role": authority_result.get("required_role", ""),
        "escalation_chain": authority_result.get("escalation_chain", []),
        "reason": authority_result.get("reason", ""),
        "context": context or {},
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "resolved_by": None,
        "resolved_at": None,
        "resolution_reason": None,
    }
    _escalation_queue.append(item)
    logger.info("escalation.created", id=item["id"], action=action, entity_id=entity_id)
    return item


async def get_queue(status: str | None = None, role: str | None = None) -> list[dict]:
    """Get escalation items, optionally filtered."""
    items = _escalation_queue
    if status:
        items = [i for i in items if i["status"] == status]
    if role:
        items = [i for i in items if role in i.get("escalation_chain", []) or i.get("required_role") == role]
    return sorted(items, key=lambda x: x["created_at"], reverse=True)


async def get_by_id(item_id: str) -> dict | None:
    """Get a single escalation item by ID."""
    for item in _escalation_queue:
        if item["id"] == item_id:
            return item
    return None


async def resolve(item_id: str, decision: str, resolved_by: str, reason: str) -> dict | None:
    """Approve or reject an escalation item."""
    for item in _escalation_queue:
        if item["id"] == item_id:
            item["status"] = decision
            item["resolved_by"] = resolved_by
            item["resolved_at"] = datetime.now(UTC).isoformat()
            item["resolution_reason"] = reason
            logger.info("escalation.resolved", id=item_id, decision=decision, by=resolved_by)
            return item
    return None


async def count_pending() -> int:
    """Count items awaiting approval."""
    return sum(1 for i in _escalation_queue if i["status"] == "pending")
