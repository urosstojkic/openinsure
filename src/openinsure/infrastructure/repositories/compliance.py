"""In-memory compliance repository for decisions and audit events."""

from __future__ import annotations

from typing import Any


class InMemoryComplianceRepository:
    """Dict/list-backed compliance store for local development and testing."""

    def __init__(self) -> None:
        self._decisions: dict[str, dict[str, Any]] = {}
        self._audit_events: list[dict[str, Any]] = []

    # -- decisions -----------------------------------------------------------

    async def add_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        self._decisions[decision["id"]] = decision
        return decision

    async def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        return self._decisions.get(decision_id)

    async def list_decisions(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = list(self._decisions.values())
        for key, val in (filters or {}).items():
            if val is not None:
                results = [r for r in results if r.get(key) == val]
        total = len(results)
        return results[skip : skip + limit], total

    async def count_decisions(self, filters: dict[str, Any] | None = None) -> int:
        _, total = await self.list_decisions(filters=filters, skip=0, limit=len(self._decisions) or 1)
        return total

    # -- audit events --------------------------------------------------------

    async def add_audit_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self._audit_events.append(event)
        return event

    async def list_audit_events(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = list(self._audit_events)
        for key, val in (filters or {}).items():
            if val is not None:
                results = [r for r in results if r.get(key) == val]
        total = len(results)
        return results[skip : skip + limit], total

    async def clear_audit_events(self) -> None:
        self._audit_events.clear()

    # -- agent-level persistence (wired from agents.base → Foundry flow) ------

    async def store_decision(self, record: dict[str, Any]) -> str:
        """Persist an agent DecisionRecord to the in-memory store."""
        from uuid import uuid4

        record_id = str(record.get("decision_id", record.get("id", uuid4())))
        entry = {
            "id": record_id,
            "decision_type": record.get("decision_type", ""),
            "entity_id": record.get("entity_id", record.get("agent_id", "")),
            "entity_type": record.get("entity_type", "agent"),
            "model_id": record.get("model_used", record.get("model_id", "")),
            "model_version": record.get("model_version", ""),
            "input_summary": record.get("input_summary", {}),
            "output_summary": record.get("output", record.get("output_summary", {})),
            "confidence": record.get("confidence", 0),
            "explanation": str(record.get("reasoning", "")),
            "human_override": bool(record.get("human_override", False)),
            "override_reason": record.get("override_reason"),
            "created_at": record.get("created_at", record.get("timestamp", "")),
        }
        self._decisions[record_id] = entry
        return record_id

    async def store_audit_event(self, event: dict[str, Any]) -> str:
        """Persist an audit event from the agent workflow."""
        from uuid import uuid4

        event_id = str(event.get("id", uuid4()))
        entry = {
            "id": event_id,
            "timestamp": event.get("timestamp", event.get("created_at", "")),
            "actor": event.get("actor", event.get("actor_id", "agent")),
            "action": event.get("action", ""),
            "entity_type": event.get("entity_type", event.get("resource_type", "")),
            "entity_id": event.get("entity_id", event.get("resource_id", "")),
            "details": event.get("details", {}),
        }
        self._audit_events.append(entry)
        return event_id
