"""Party resolution service for customer deduplication.

Matches incoming applicant data against existing parties to prevent
duplicates and maintain a single customer record across submissions,
policies, and claims.

Issue #157 — Customer/Applicant Deduplication.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from openinsure.infrastructure.factory import (
    get_claim_repository,
    get_policy_repository,
    get_submission_repository,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory party store (used when storage_mode="memory")
# ---------------------------------------------------------------------------
_party_store: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PartyResolutionService:
    """Resolve applicant data to an existing or new party record.

    Match priority:
    1. Exact match by ``tax_id`` (if provided)
    2. Exact match by ``registration_number`` (if provided)
    3. Exact match by ``name`` (case-insensitive)
    4. No match → create new party
    """

    async def resolve_or_create(self, applicant_data: dict[str, Any]) -> str:
        """Match an existing party or create a new one. Returns ``party_id``."""
        name = applicant_data.get("name", "").strip()
        tax_id = applicant_data.get("tax_id", "").strip() or None
        reg_number = applicant_data.get("registration_number", "").strip() or None

        # 1. Exact match by tax_id
        if tax_id:
            for party in _party_store.values():
                if party.get("tax_id") and party["tax_id"] == tax_id:
                    logger.info(
                        "party_resolution.matched_by_tax_id",
                        party_id=party["id"],
                        tax_id=tax_id,
                    )
                    return str(party["id"])

        # 2. Exact match by registration_number
        if reg_number:
            for party in _party_store.values():
                if (
                    party.get("registration_number")
                    and party["registration_number"] == reg_number
                ):
                    logger.info(
                        "party_resolution.matched_by_registration_number",
                        party_id=party["id"],
                        registration_number=reg_number,
                    )
                    return str(party["id"])

        # 3. Exact match by name (case-insensitive)
        if name:
            name_lower = name.lower()
            for party in _party_store.values():
                if party.get("name", "").lower() == name_lower:
                    logger.info(
                        "party_resolution.matched_by_name",
                        party_id=party["id"],
                        name=name,
                    )
                    return str(party["id"])

        # 4. No match → create new party
        party_id = str(uuid.uuid4())
        now = _now()
        new_party: dict[str, Any] = {
            "id": party_id,
            "name": name or "Unknown",
            "party_type": applicant_data.get("party_type", "organization"),
            "roles": applicant_data.get("roles", ["insured"]),
            "tax_id": tax_id,
            "registration_number": reg_number,
            "addresses": applicant_data.get("addresses", []),
            "contacts": applicant_data.get("contacts", []),
            "relationships": {},
            "risk_profiles": [],
            "created_at": now,
            "updated_at": now,
        }
        _party_store[party_id] = new_party
        logger.info(
            "party_resolution.created_new_party",
            party_id=party_id,
            name=name,
        )
        return party_id

    async def get_party(self, party_id: str) -> dict[str, Any] | None:
        """Return a party record by ID, or ``None`` if not found."""
        return _party_store.get(party_id)

    async def search_parties(
        self,
        name: str | None = None,
        tax_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search parties by name (case-insensitive prefix) or tax_id."""
        results: list[dict[str, Any]] = []
        for party in _party_store.values():
            if tax_id and party.get("tax_id") == tax_id:
                results.append(party)
                continue
            if name and party.get("name", "").lower().startswith(name.lower()):
                results.append(party)
                continue
        return results[:limit]

    async def get_customer_360(self, party_id: str) -> dict[str, Any]:
        """Get all submissions, policies, and claims for a customer.

        Returns a consolidated view of all insurance activity linked
        to the given party.
        """
        party = _party_store.get(party_id)
        if party is None:
            return {"error": "Party not found", "party_id": party_id}

        # Gather linked submissions
        sub_repo = get_submission_repository()
        all_subs = await sub_repo.list_all(limit=1000)
        linked_submissions = [
            s for s in all_subs if s.get("applicant_id") == party_id
        ]

        # Gather linked policies
        pol_repo = get_policy_repository()
        all_pols = await pol_repo.list_all(limit=1000)
        linked_policies = [
            p for p in all_pols if p.get("insured_id") == party_id
        ]

        # Gather linked claims
        claim_repo = get_claim_repository()
        all_claims = await claim_repo.list_all(limit=1000)
        policy_ids = {p.get("id") for p in linked_policies}
        linked_claims = [
            c for c in all_claims if c.get("policy_id") in policy_ids
        ]

        return {
            "party": party,
            "submissions": linked_submissions,
            "policies": linked_policies,
            "claims": linked_claims,
            "summary": {
                "total_submissions": len(linked_submissions),
                "total_policies": len(linked_policies),
                "total_claims": len(linked_claims),
            },
        }


# Module-level singleton
_service: PartyResolutionService | None = None


def get_party_resolution_service() -> PartyResolutionService:
    """Return a shared PartyResolutionService instance."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = PartyResolutionService()
    return _service
