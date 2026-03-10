"""Submission repository implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openinsure.infrastructure.repository import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class InMemorySubmissionRepository(BaseRepository):
    """Dict-backed submission store for local development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    # -- mutations -----------------------------------------------------------

    async def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        self._store[entity["id"]] = entity
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            event_type="submission.received",
            subject=f"/submissions/{entity.get('id', '')}",
            data={"submission_id": entity.get("id"), "status": entity.get("status")},
        )
        return entity

    async def update(self, entity_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any] | None:
        from openinsure.domain.state_machine import (
            validate_submission_invariants,
            validate_submission_transition,
        )

        record = self._store.get(str(entity_id))
        if record is None:
            return None
        if "status" in updates and record.get("status"):
            validate_submission_transition(record["status"], updates["status"])
        merged = {**record, **updates}
        validate_submission_invariants(merged)
        record.update(updates)
        return record

    async def delete(self, entity_id: UUID | str) -> bool:
        return self._store.pop(str(entity_id), None) is not None

    # -- queries -------------------------------------------------------------

    async def get_by_id(self, entity_id: UUID | str) -> dict[str, Any] | None:
        return self._store.get(str(entity_id))

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = list(self._store.values())
        for key, val in (filters or {}).items():
            if val is not None:
                if key.endswith("_gte"):
                    field = key[: -len("_gte")]
                    results = [r for r in results if r.get(field, "") >= val]
                elif key.endswith("_lte"):
                    field = key[: -len("_lte")]
                    results = [r for r in results if r.get(field, "") <= val]
                else:
                    results = [r for r in results if r.get(key) == val]
        return results[skip : skip + limit]

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        if not filters:
            return len(self._store)
        results = list(self._store.values())
        for key, val in filters.items():
            if val is not None:
                if key.endswith("_gte"):
                    field = key[: -len("_gte")]
                    results = [r for r in results if r.get(field, "") >= val]
                elif key.endswith("_lte"):
                    field = key[: -len("_lte")]
                    results = [r for r in results if r.get(field, "") <= val]
                else:
                    results = [r for r in results if r.get(key) == val]
        return len(results)

    # -- convenience ---------------------------------------------------------

    async def update_status(
        self, entity_id: UUID | str, status: str, extra: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        from openinsure.domain.state_machine import (
            validate_submission_invariants,
            validate_submission_transition,
        )

        record = self._store.get(str(entity_id))
        if record is None:
            return None
        if record.get("status"):
            validate_submission_transition(record["status"], status)
        merged = {**record, "status": status, **(extra or {})}
        validate_submission_invariants(merged)
        record["status"] = status
        if extra:
            record.update(extra)
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            event_type=f"submission.{status}",
            subject=f"/submissions/{entity_id}",
            data={"submission_id": str(entity_id), "status": status},
        )
        return record
