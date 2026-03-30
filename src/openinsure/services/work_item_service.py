"""Work item service — structured task tracking with SLA.

Provides inbox-style work queues for underwriters, claims adjusters,
and other platform personas. Each work item tracks an entity, has an
owner, priority, due date, and SLA.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()

# In-memory store (production → SQL via work_items table)
_work_items: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def create_work_item(
    *,
    entity_type: str,
    entity_id: str,
    work_type: str,
    title: str,
    description: str | None = None,
    assigned_to: str | None = None,
    assigned_role: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
    sla_hours: int | None = None,
) -> dict[str, Any]:
    """Create a new work item."""
    if priority not in ("low", "medium", "high", "urgent"):
        msg = f"Invalid priority: {priority}"
        raise ValueError(msg)

    # Auto-calculate due_date from SLA if not provided
    computed_due = due_date
    if not computed_due and sla_hours:
        computed_due = (datetime.now(UTC) + timedelta(hours=sla_hours)).isoformat()

    item = {
        "id": str(uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "work_type": work_type,
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "assigned_role": assigned_role,
        "priority": priority,
        "status": "open",
        "due_date": computed_due,
        "sla_hours": sla_hours,
        "completed_at": None,
        "completed_by": None,
        "created_at": _now(),
    }
    _work_items.append(item)
    logger.info(
        "work_item.created",
        work_item_id=item["id"],
        entity_type=entity_type,
        entity_id=entity_id,
        work_type=work_type,
        assigned_to=assigned_to,
    )
    return item


async def complete_work_item(
    item_id: str,
    completed_by: str,
) -> dict[str, Any] | None:
    """Mark a work item as completed."""
    for item in _work_items:
        if item["id"] == item_id:
            if item["status"] == "completed":
                msg = f"Work item {item_id} is already completed"
                raise ValueError(msg)
            item["status"] = "completed"
            item["completed_at"] = _now()
            item["completed_by"] = completed_by
            logger.info(
                "work_item.completed",
                work_item_id=item_id,
                completed_by=completed_by,
            )
            return item
    return None


async def get_inbox(
    assigned_to: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Get work items for a user (their inbox)."""
    items = [i for i in _work_items if i["assigned_to"] == assigned_to]
    if status:
        items = [i for i in items if i["status"] == status]
    else:
        # Default: show open and in_progress items
        items = [i for i in items if i["status"] in ("open", "in_progress")]
    return sorted(items, key=lambda x: x["created_at"], reverse=True)


async def get_work_item_by_id(item_id: str) -> dict[str, Any] | None:
    """Get a single work item by ID."""
    for item in _work_items:
        if item["id"] == item_id:
            return item
    return None


async def list_work_items(
    entity_type: str | None = None,
    entity_id: str | None = None,
    status: str | None = None,
    assigned_to: str | None = None,
) -> list[dict[str, Any]]:
    """List work items with optional filtering."""
    items = list(_work_items)
    if entity_type:
        items = [i for i in items if i["entity_type"] == entity_type]
    if entity_id:
        items = [i for i in items if i["entity_id"] == entity_id]
    if status:
        items = [i for i in items if i["status"] == status]
    if assigned_to:
        items = [i for i in items if i["assigned_to"] == assigned_to]
    return sorted(items, key=lambda x: x["created_at"], reverse=True)
