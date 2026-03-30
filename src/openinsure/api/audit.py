"""Audit trail API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from openinsure.infrastructure.factory import get_audit_service

router = APIRouter()


@router.get("/{entity_type}/{entity_id}")
async def get_entity_audit_history(entity_type: str, entity_id: str) -> dict:
    """Return the full audit history for a single entity."""
    svc = get_audit_service()
    history = await svc.get_history(entity_type, entity_id)
    return {"entity_type": entity_type, "entity_id": entity_id, "history": history}


@router.get("/recent")
async def get_recent_changes(hours: int = Query(default=24, ge=1, le=720)) -> dict:
    """Return recent changes across all entities."""
    svc = get_audit_service()
    changes = await svc.get_recent(hours)
    return {"hours": hours, "count": len(changes), "changes": changes}
