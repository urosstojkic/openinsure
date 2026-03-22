"""Submission business logic service.

Encapsulates triage, quoting, and binding logic extracted from API handlers.
API handlers delegate to this service to keep endpoint code thin.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from openinsure.infrastructure.factory import (
    get_billing_repository,
    get_policy_repository,
    get_submission_repository,
)
from openinsure.rbac.authority import AuthorityDecision, AuthorityEngine

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SubmissionService:
    """Service encapsulating submission business logic."""

    def __init__(self) -> None:
        self._repo = get_submission_repository()

    async def run_triage(self, submission_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Execute triage logic: assess risk appetite and advance to underwriting.

        Returns a dict with keys: status, risk_score, recommendation, flags.
        """
        from openinsure.agents.foundry_client import get_foundry_client

        foundry = get_foundry_client()

        if foundry.is_available:
            result = await foundry.invoke(
                "openinsure-submission",
                "You are triaging a cyber insurance submission. Our appetite accepts:\n"
                "- IT/Tech (SIC 7xxx), Financial (SIC 6xxx), Professional Services\n"
                "- Revenue $500K to $50M\n"
                "- Security maturity score 4+ out of 10\n"
                "- Max 3 prior incidents\n\n"
                "Respond ONLY with JSON:\n"
                '{"appetite_match": "yes", "risk_score": 5, "priority": "medium", '
                '"confidence": 0.9, "reasoning": "..."}\n\n'
                f"Submission:\n{json.dumps(record, default=str)[:1000]}",
            )
            resp = result.get("response", {})
            if isinstance(resp, dict) and result.get("source") == "foundry":
                appetite = str(resp.get("appetite_match", "yes")).lower()
                recommendation = "decline" if appetite in ("no", "decline") else "proceed_to_quote"
                flags: list[str] = []
                if resp.get("reasoning"):
                    flags.append(str(resp["reasoning"]))

                await self._repo.update(
                    submission_id,
                    {
                        "status": "underwriting",
                        "triage_result": json.dumps(resp),
                        "updated_at": _now(),
                    },
                )
                return {
                    "status": "underwriting",
                    "risk_score": float(resp.get("risk_score", 5)),
                    "recommendation": recommendation,
                    "flags": flags,
                    "triage_result": resp,
                }

        # Local fallback
        fallback = {"risk_score": 0.42, "recommendation": "proceed_to_quote", "source": "local"}
        await self._repo.update(
            submission_id,
            {
                "status": "underwriting",
                "triage_result": json.dumps(fallback),
                "updated_at": _now(),
            },
        )
        return {
            "status": "underwriting",
            "risk_score": 0.42,
            "recommendation": "proceed_to_quote",
            "flags": [],
            "triage_result": fallback,
        }

    async def calculate_premium(self, submission_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Calculate premium for a submission.

        Returns dict with: premium, coverages, authority_result.
        """
        from openinsure.agents.foundry_client import get_foundry_client

        foundry = get_foundry_client()
        premium = 5000.0

        if foundry.is_available:
            result = await foundry.invoke(
                "openinsure-underwriting",
                "Price this cyber insurance submission. Calculate premium.\n"
                "Base: $1.50 per $1000 revenue. Adjust for industry, security, incidents.\n"
                "Respond ONLY with JSON:\n"
                '{"risk_score": 35, "recommended_premium": 12500, "confidence": 0.85}\n\n'
                f"Submission:\n{json.dumps(record, default=str)[:800]}",
            )
            resp = result.get("response", {})
            if isinstance(resp, dict) and "recommended_premium" in resp:
                raw_premium = resp["recommended_premium"]
                premium = float(raw_premium) if raw_premium is not None else 5000.0
                premium = premium or 5000.0

        await self._repo.update(
            submission_id,
            {"status": "quoted", "quoted_premium": premium, "updated_at": _now()},
        )
        return {
            "premium": premium,
            "coverages": [{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
        }

    async def bind_policy(self, submission_id: str, record: dict[str, Any], user_role: str) -> dict[str, Any]:
        """Bind a submission to a policy: create policy, billing, cessions.

        Returns dict with: policy_id, policy_number, premium, authority_result.
        """
        premium = record.get("quoted_premium", 0) or record.get("total_premium", 10000)
        policy_id = str(uuid.uuid4())
        policy_number = f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"

        # Authority check
        engine = AuthorityEngine()
        cyber_data = record.get("risk_data", {})
        if isinstance(cyber_data, str):
            try:
                cyber_data = json.loads(cyber_data)
            except (json.JSONDecodeError, TypeError):
                cyber_data = {}
        limit = Decimal(str(cyber_data.get("requested_limit", 1000000) if cyber_data else 1000000))
        auth_result = engine.check_bind_authority(Decimal(str(premium)), user_role, limit)

        if auth_result.decision == AuthorityDecision.ESCALATE:
            return {
                "policy_id": None,
                "policy_number": None,
                "premium": premium,
                "authority_result": auth_result,
                "escalated": True,
            }

        # Create policy
        policy_repo = get_policy_repository()
        now = _now()
        applicant = record.get("applicant_name", "") or record.get("insured_name", "Unknown Insured")
        policy_data = {
            "id": policy_id,
            "policy_number": policy_number,
            "policyholder_name": applicant,
            "status": "active",
            "product_id": record.get("product_id", "cyber-smb"),
            "submission_id": record.get("id", ""),
            "insured_name": applicant,
            "effective_date": str(record.get("requested_effective_date", now)),
            "expiration_date": str(record.get("requested_expiration_date", now)),
            "premium": premium,
            "total_premium": premium,
            "written_premium": premium,
            "earned_premium": 0,
            "unearned_premium": premium,
            "lob": record.get("line_of_business", "cyber"),
            "coverages": [],
            "endorsements": [],
            "metadata": {"lob": record.get("line_of_business", "cyber"), "source": "service"},
            "documents": [],
            "bound_at": now,
            "created_at": now,
            "updated_at": now,
        }
        await policy_repo.create(policy_data)

        # Create billing
        billing_repo = get_billing_repository()
        await billing_repo.create(
            {
                "id": str(uuid.uuid4()),
                "policy_id": policy_id,
                "billing_plan": "direct_bill",
                "total_premium": premium,
                "balance_due": premium,
                "created_at": now,
                "updated_at": now,
            }
        )

        # Update submission
        await self._repo.update(submission_id, {"status": "bound", "updated_at": now})

        # Auto-cession (best-effort)
        try:
            self._auto_cession(policy_id, policy_number, policy_data)
        except Exception:
            logger.warning("submission_service.auto_cession_failed", exc_info=True)

        return {
            "policy_id": policy_id,
            "policy_number": policy_number,
            "premium": premium,
            "authority_result": auth_result,
            "escalated": False,
        }

    @staticmethod
    def _auto_cession(policy_id: str, policy_number: str, policy_data: dict[str, Any]) -> None:
        """Attempt auto-cession calculation (synchronous helper)."""
        # This is a best-effort operation; failures don't block binding
