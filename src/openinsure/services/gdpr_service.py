"""GDPR compliance service for OpenInsure.

Implements key GDPR rights:
- Art 7: Consent tracking
- Art 17: Right to erasure (anonymisation)
- Art 20: Data portability (export)

Issue #165 — GDPR Compliance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from openinsure.infrastructure.factory import (
    get_policy_repository,
)
from openinsure.services.party_resolution import get_party_resolution_service

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores (used when storage_mode="memory")
# ---------------------------------------------------------------------------
_consent_store: dict[str, dict[str, Any]] = {}
_retention_policies: list[dict[str, Any]] = [
    {
        "id": str(uuid.uuid4()),
        "entity_type": "policies",
        "retention_years": 10,
        "legal_basis": "Insurance regulation — record retention",
        "auto_anonymize": True,
    },
    {
        "id": str(uuid.uuid4()),
        "entity_type": "claims",
        "retention_years": 10,
        "legal_basis": "Insurance regulation — claims records",
        "auto_anonymize": True,
    },
    {
        "id": str(uuid.uuid4()),
        "entity_type": "submissions",
        "retention_years": 7,
        "legal_basis": "Business records retention",
        "auto_anonymize": True,
    },
    {
        "id": str(uuid.uuid4()),
        "entity_type": "parties",
        "retention_years": 10,
        "legal_basis": "Insurance regulation — customer records",
        "auto_anonymize": True,
    },
]
_erasure_log: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(UTC).isoformat()


class GDPRService:
    """GDPR compliance operations."""

    # -- Art 17: Right to erasure -----------------------------------------------

    async def process_erasure_request(self, party_id: str) -> dict[str, Any]:
        """Art 17: Right to erasure — anonymise PII, keep financial records.

        Checks for active policies that legally block erasure.
        Replaces PII with ``[REDACTED]`` and logs the action.
        """
        svc = get_party_resolution_service()
        party = await svc.get_party(party_id)
        if party is None:
            return {"status": "error", "detail": "Party not found"}

        # Check for active policies — block erasure if any exist
        pol_repo = get_policy_repository()
        all_policies = await pol_repo.list_all(limit=1000)
        active_policies = [
            p
            for p in all_policies
            if p.get("insured_id") == party_id
            and p.get("status") in ("active", "pending")
        ]
        if active_policies:
            return {
                "status": "blocked",
                "detail": "Cannot erase: party has active policies",
                "active_policy_count": len(active_policies),
                "party_id": party_id,
            }

        # Anonymise PII fields
        original_name = party.get("name", "")
        party["name"] = "[REDACTED]"
        party["tax_id"] = None
        party["registration_number"] = None
        party["addresses"] = []
        party["contacts"] = []
        party["updated_at"] = _now()

        # Log the erasure
        erasure_record = {
            "id": str(uuid.uuid4()),
            "party_id": party_id,
            "action": "erasure",
            "original_name": original_name,
            "performed_at": _now(),
            "fields_anonymised": [
                "name",
                "tax_id",
                "registration_number",
                "addresses",
                "contacts",
            ],
        }
        _erasure_log.append(erasure_record)

        logger.info(
            "gdpr.erasure_completed",
            party_id=party_id,
            fields_anonymised=erasure_record["fields_anonymised"],
        )
        return {
            "status": "completed",
            "party_id": party_id,
            "fields_anonymised": erasure_record["fields_anonymised"],
            "performed_at": erasure_record["performed_at"],
        }

    # -- Art 20: Data portability -----------------------------------------------

    async def export_personal_data(self, party_id: str) -> dict[str, Any]:
        """Art 20: Data portability — export all personal data as JSON.

        Gathers party info, addresses, contacts, linked submissions,
        policies, and claims.
        """
        svc = get_party_resolution_service()
        customer_360 = await svc.get_customer_360(party_id)
        if "error" in customer_360:
            return {"status": "error", "detail": "Party not found"}

        party = customer_360["party"]
        return {
            "status": "completed",
            "party_id": party_id,
            "exported_at": _now(),
            "personal_data": {
                "name": party.get("name"),
                "party_type": party.get("party_type"),
                "tax_id": party.get("tax_id"),
                "registration_number": party.get("registration_number"),
                "addresses": party.get("addresses", []),
                "contacts": party.get("contacts", []),
            },
            "insurance_data": {
                "submissions": [
                    {
                        "id": s.get("id"),
                        "status": s.get("status"),
                        "line_of_business": s.get("line_of_business"),
                        "created_at": s.get("created_at"),
                    }
                    for s in customer_360.get("submissions", [])
                ],
                "policies": [
                    {
                        "id": p.get("id"),
                        "status": p.get("status"),
                        "effective_date": p.get("effective_date"),
                        "expiration_date": p.get("expiration_date"),
                    }
                    for p in customer_360.get("policies", [])
                ],
                "claims": [
                    {
                        "id": c.get("id"),
                        "status": c.get("status"),
                        "loss_date": c.get("loss_date"),
                    }
                    for c in customer_360.get("claims", [])
                ],
            },
        }

    # -- Art 7: Consent tracking ------------------------------------------------

    async def get_consent_status(self, party_id: str) -> list[dict[str, Any]]:
        """Art 7: Return all consent records for a party."""
        return [
            c
            for c in _consent_store.values()
            if c.get("party_id") == party_id
        ]

    async def grant_consent(
        self,
        party_id: str,
        purpose: str,
        evidence: str = "",
    ) -> dict[str, Any]:
        """Record a consent grant."""
        # Withdraw any existing active consent for same purpose
        for consent in _consent_store.values():
            if (
                consent.get("party_id") == party_id
                and consent.get("purpose") == purpose
                and consent.get("status") == "granted"
            ):
                consent["status"] = "withdrawn"
                consent["withdrawn_at"] = _now()

        consent_id = str(uuid.uuid4())
        now = _now()
        record: dict[str, Any] = {
            "id": consent_id,
            "party_id": party_id,
            "purpose": purpose,
            "status": "granted",
            "granted_at": now,
            "withdrawn_at": None,
            "expires_at": None,
            "evidence": evidence,
            "created_at": now,
        }
        _consent_store[consent_id] = record
        logger.info(
            "gdpr.consent_granted",
            party_id=party_id,
            purpose=purpose,
        )
        return record

    async def withdraw_consent(
        self,
        party_id: str,
        purpose: str,
    ) -> dict[str, Any]:
        """Record a consent withdrawal."""
        withdrawn_count = 0
        for consent in _consent_store.values():
            if (
                consent.get("party_id") == party_id
                and consent.get("purpose") == purpose
                and consent.get("status") == "granted"
            ):
                consent["status"] = "withdrawn"
                consent["withdrawn_at"] = _now()
                withdrawn_count += 1

        logger.info(
            "gdpr.consent_withdrawn",
            party_id=party_id,
            purpose=purpose,
            withdrawn_count=withdrawn_count,
        )
        return {
            "party_id": party_id,
            "purpose": purpose,
            "status": "withdrawn",
            "withdrawn_count": withdrawn_count,
            "withdrawn_at": _now(),
        }

    # -- Retention policies -----------------------------------------------------

    async def list_retention_policies(self) -> list[dict[str, Any]]:
        """Return all data retention policies."""
        return list(_retention_policies)


# Module-level singleton
_gdpr_service: GDPRService | None = None


def get_gdpr_service() -> GDPRService:
    """Return a shared GDPRService instance."""
    global _gdpr_service  # noqa: PLW0603
    if _gdpr_service is None:
        _gdpr_service = GDPRService()
    return _gdpr_service
