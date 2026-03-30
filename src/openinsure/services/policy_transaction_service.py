"""Policy transaction service — records every policy mutation.

Every state change (bind, endorse, renew, cancel, reinstate) creates an
immutable transaction record. The current state of a policy is the
cumulative effect of all its transactions, enabling time-travel queries.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()

# In-memory store (production → SQL via policy_transactions table)
_transactions: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def record_transaction(
    *,
    policy_id: str,
    transaction_type: str,
    effective_date: date | str,
    expiration_date: date | str | None = None,
    premium_change: float = 0.0,
    description: str | None = None,
    coverages_snapshot: list[dict[str, Any]] | None = None,
    terms_snapshot: dict[str, Any] | None = None,
    created_by: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Record a policy transaction."""
    txn = {
        "id": str(uuid4()),
        "policy_id": policy_id,
        "transaction_type": transaction_type,
        "effective_date": str(effective_date),
        "expiration_date": str(expiration_date) if expiration_date else None,
        "premium_change": premium_change,
        "description": description,
        "coverages_snapshot": json.dumps(coverages_snapshot) if coverages_snapshot else None,
        "terms_snapshot": json.dumps(terms_snapshot) if terms_snapshot else None,
        "created_by": created_by,
        "created_at": _now(),
        "version": version,
    }
    _transactions.append(txn)
    logger.info(
        "policy_transaction.recorded",
        policy_id=policy_id,
        transaction_type=transaction_type,
        premium_change=premium_change,
    )
    return txn


async def get_transactions(policy_id: str) -> list[dict[str, Any]]:
    """Get all transactions for a policy, ordered by effective date."""
    txns = [t for t in _transactions if t["policy_id"] == policy_id]
    return sorted(txns, key=lambda t: t["effective_date"])


async def get_transaction_by_id(transaction_id: str) -> dict[str, Any] | None:
    """Get a single transaction by ID."""
    for t in _transactions:
        if t["id"] == transaction_id:
            return t
    return None
