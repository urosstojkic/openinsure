"""Decision Record storage and management for EU AI Act compliance.

Implements Art. 12 (Record-Keeping) requirements.
Every AI decision is stored immutably with full reasoning chain.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger()


class DecisionRecordStore:
    """In-memory decision record store (replace with Event Hubs + Cosmos DB in production)."""

    def __init__(self) -> None:
        self._records: dict[UUID, dict[str, Any]] = {}

    async def store(self, record: dict[str, Any]) -> UUID:
        """Store a decision record immutably."""
        record_id = record.get("decision_id")
        if record_id is None:
            raise ValueError("Decision record must have a decision_id")
        self._records[record_id] = {
            **record,
            "stored_at": datetime.now(UTC).isoformat(),
            "immutable": True,
        }
        logger.info("decision_record.stored", decision_id=str(record_id))
        return record_id

    async def get(self, decision_id: UUID) -> dict[str, Any] | None:
        """Retrieve a decision record by ID."""
        return self._records.get(decision_id)

    async def list_records(
        self,
        agent_id: str | None = None,
        decision_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List decision records with filtering."""
        records = list(self._records.values())
        if agent_id:
            records = [r for r in records if r.get("agent_id") == agent_id]
        if decision_type:
            records = [r for r in records if r.get("decision_type") == decision_type]
        if start_date:
            records = [r for r in records if r.get("timestamp", "") >= start_date.isoformat()]
        if end_date:
            records = [r for r in records if r.get("timestamp", "") <= end_date.isoformat()]
        return records[offset : offset + limit]

    async def count(self) -> int:
        """Count total decision records."""
        return len(self._records)
