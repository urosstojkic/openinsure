"""Claims business logic service.

Encapsulates reserve setting, payment recording, and closure logic
extracted from API handlers.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from openinsure.infrastructure.factory import get_claim_repository
from openinsure.rbac.authority import AuthorityDecision, AuthorityEngine

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ClaimsService:
    """Service encapsulating claims business logic."""

    def __init__(self) -> None:
        self._repo = get_claim_repository()

    async def set_reserve(
        self,
        claim_id: str,
        record: dict[str, Any],
        category: str,
        amount: float,
        currency: str,
        notes: str | None,
        user_role: str,
    ) -> dict[str, Any]:
        """Set or update reserves on a claim with authority check.

        Returns dict with: reserve_id, total_reserved, authority_result.
        """
        engine = AuthorityEngine()
        auth_result = engine.check_reserve_authority(Decimal(str(amount)), user_role)

        if auth_result.decision == AuthorityDecision.ESCALATE:
            return {
                "reserve_id": None,
                "total_reserved": record.get("total_reserved", 0),
                "authority_result": auth_result,
                "escalated": True,
            }

        rid = str(uuid.uuid4())
        now = _now()
        reserve_entry = {
            "reserve_id": rid,
            "category": category,
            "amount": amount,
            "currency": currency,
            "notes": notes,
            "created_at": now,
        }

        record.setdefault("reserves", []).append(reserve_entry)
        record["total_reserved"] = sum(r["amount"] for r in record["reserves"])
        if record.get("status") == "reported":
            record["status"] = "reserved"
        record["updated_at"] = now

        return {
            "reserve_id": rid,
            "total_reserved": record["total_reserved"],
            "authority_result": auth_result,
            "escalated": False,
            "created_at": now,
        }

    async def record_payment(
        self,
        claim_id: str,
        record: dict[str, Any],
        payee: str,
        amount: float,
        currency: str,
        category: str,
        reference: str | None,
        notes: str | None,
        user_role: str,
    ) -> dict[str, Any]:
        """Record a payment on a claim with authority check.

        Returns dict with: payment_id, total_paid, authority_result.
        """
        engine = AuthorityEngine()
        auth_result = engine.check_settlement_authority(Decimal(str(amount)), user_role)

        if auth_result.decision == AuthorityDecision.ESCALATE:
            return {
                "payment_id": None,
                "total_paid": record.get("total_paid", 0),
                "authority_result": auth_result,
                "escalated": True,
            }

        pid = str(uuid.uuid4())
        now = _now()
        payment_entry = {
            "payment_id": pid,
            "payee": payee,
            "amount": amount,
            "currency": currency,
            "category": category,
            "reference": reference,
            "notes": notes,
            "created_at": now,
        }

        record.setdefault("payments", []).append(payment_entry)
        record["total_paid"] = sum(p["amount"] for p in record["payments"])
        if record.get("status") in {"reported", "reserved"}:
            record["status"] = "approved"
        record["updated_at"] = now

        return {
            "payment_id": pid,
            "total_paid": record["total_paid"],
            "authority_result": auth_result,
            "escalated": False,
            "created_at": now,
        }

    async def close_claim(
        self, claim_id: str, record: dict[str, Any], reason: str, outcome: str, user_role: str
    ) -> dict[str, Any]:
        """Close a claim with settlement authority check.

        Returns dict with: closed_at, authority_result.
        """
        engine = AuthorityEngine()
        settlement_amount = Decimal(str(record.get("total_paid", 0)))
        auth_result = engine.check_settlement_authority(settlement_amount, user_role)

        if auth_result.decision == AuthorityDecision.ESCALATE:
            return {
                "closed_at": None,
                "authority_result": auth_result,
                "escalated": True,
            }

        now = _now()
        record["status"] = "closed"
        record["updated_at"] = now

        return {
            "closed_at": now,
            "authority_result": auth_result,
            "escalated": False,
        }
