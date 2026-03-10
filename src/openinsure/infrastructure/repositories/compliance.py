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
