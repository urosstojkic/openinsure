"""Data-level audit trail service.

Records every create / update / delete / restore operation on domain
entities into the ``change_log`` table for compliance and traceability.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

logger = logging.getLogger(__name__)


class AuditService:
    """Thin service that writes and reads the ``change_log`` table."""

    def __init__(self, db: DatabaseAdapter | None = None) -> None:
        self.db = db

    async def log_change(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        changed_by: str,
        changes: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Insert a row into change_log.  No-op when DB is unavailable."""
        if self.db is None:
            logger.debug("AuditService: no DB configured — skipping log_change")
            return
        # Map domain actions to DB-allowed values; preserve original in changes
        _allowed_actions = {"create", "update", "delete", "restore", "anonymize"}
        db_action = action
        if action not in _allowed_actions:
            if changes is None:
                changes = {}
            changes["_original_action"] = action
            db_action = "update"
        try:
            await self.db.execute_query(
                """INSERT INTO change_log
                   (id, entity_type, entity_id, action, changed_by,
                    changed_at, changes, reason, ip_address)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    str(uuid4()),
                    entity_type,
                    entity_id,
                    db_action,
                    changed_by,
                    datetime.now(UTC).isoformat(),
                    json.dumps(changes) if changes else None,
                    reason,
                    ip_address,
                ],
            )
        except Exception:
            logger.warning(
                "AuditService: failed to log %s on %s/%s",
                action,
                entity_type,
                entity_id,
                exc_info=True,
            )

    async def get_history(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        """Return audit history for a specific entity, newest first."""
        if self.db is None:
            return []
        rows = await self.db.fetch_all(
            """SELECT id, entity_type, entity_id, action, changed_by,
                      changed_at, changes, reason, ip_address
               FROM change_log
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY changed_at DESC""",
            [entity_type, entity_id],
        )
        return [_row_to_dict(r) for r in rows]

    async def get_recent(self, hours: int = 24) -> list[dict[str, Any]]:
        """Return recent changes across all entities."""
        if self.db is None:
            return []
        rows = await self.db.fetch_all(
            """SELECT id, entity_type, entity_id, action, changed_by,
                      changed_at, changes, reason, ip_address
               FROM change_log
               WHERE changed_at >= DATEADD(HOUR, -?, GETUTCDATE())
               ORDER BY changed_at DESC""",
            [hours],
        )
        return [_row_to_dict(r) for r in rows]


def _str(val: Any) -> str:
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    changes_raw = row.get("changes")
    if isinstance(changes_raw, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            changes_raw = json.loads(changes_raw)
    return {
        "id": _str(row.get("id")),
        "entity_type": _str(row.get("entity_type")),
        "entity_id": _str(row.get("entity_id")),
        "action": _str(row.get("action")),
        "changed_by": _str(row.get("changed_by")),
        "changed_at": _str(row.get("changed_at")),
        "changes": changes_raw,
        "reason": _str(row.get("reason")) or None,
        "ip_address": _str(row.get("ip_address")) or None,
    }
