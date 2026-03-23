"""Document generation service for OpenInsure.

Produces structured JSON document content (declarations pages, certificates of
insurance, coverage schedules) from policy and submission data.  The frontend
renders the result as styled HTML / PDF-ready output.

Addresses #78: Policy Document Generation & AI-Native Document Agent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()


class DocumentGenerator:
    """Generates insurance document content from policy + submission data."""

    def generate(
        self,
        policy: dict[str, Any],
        submission: dict[str, Any],
        doc_type: str,
    ) -> dict[str, Any]:
        """Dispatch to the correct generator based on ``doc_type``."""
        generators = {
            "declaration": self._generate_declaration,
            "certificate": self._generate_certificate,
            "schedule": self._generate_schedule,
        }
        generator = generators.get(doc_type)
        if generator is None:
            raise ValueError(f"Unsupported document type: {doc_type}")
        return generator(policy, submission)

    # ------------------------------------------------------------------
    # Declarations page
    # ------------------------------------------------------------------

    def _generate_declaration(
        self,
        policy: dict[str, Any],
        submission: dict[str, Any],
    ) -> dict[str, Any]:
        insured = policy.get("policyholder_name") or policy.get("insured_name", "Unknown")
        policy_number = policy.get("policy_number", "N/A")
        effective = policy.get("effective_date", "")
        expiration = policy.get("expiration_date", "")
        premium = policy.get("premium") or policy.get("total_premium", 0)
        coverages = policy.get("coverages", [])
        endorsements = policy.get("endorsements", [])
        lob = policy.get("lob", submission.get("line_of_business", "cyber"))

        coverage_rows = []
        for cov in coverages:
            coverage_rows.append(
                {
                    "coverage_code": cov.get("coverage_code", ""),
                    "coverage_name": cov.get("coverage_name", ""),
                    "limit": cov.get("limit", 0),
                    "deductible": cov.get("deductible", 0),
                    "premium": cov.get("premium", 0),
                }
            )

        sections = [
            {
                "heading": "Named Insured",
                "content": f"This policy is issued to {insured}.",
                "data": {"insured_name": insured},
            },
            {
                "heading": "Policy Period",
                "content": (
                    f"This policy is effective from {effective} to {expiration}, "
                    "12:01 AM standard time at the insured's address."
                ),
                "data": {"effective_date": effective, "expiration_date": expiration},
            },
            {
                "heading": "Coverage Summary",
                "content": (
                    f"The following {lob.replace('_', ' ').title()} coverages are provided "
                    "subject to the terms, conditions, and exclusions of this policy."
                ),
                "data": {"coverages": coverage_rows},
            },
            {
                "heading": "Premium",
                "content": f"Total annual premium: ${premium:,.2f}",
                "data": {
                    "total_premium": premium,
                    "premium_breakdown": coverage_rows,
                },
            },
        ]

        if endorsements:
            sections.append(
                {
                    "heading": "Endorsements",
                    "content": "The following endorsements are attached to this policy.",
                    "data": {"endorsements": endorsements},
                }
            )

        return {
            "title": f"Declarations Page — {policy_number}",
            "document_type": "declaration",
            "policy_number": policy_number,
            "sections": sections,
            "effective_date": effective,
            "summary": (
                f"Declarations page for {lob.replace('_', ' ').title()} policy "
                f"{policy_number} issued to {insured}, effective {effective} to "
                f"{expiration}, with total premium of ${premium:,.2f}."
            ),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Certificate of Insurance
    # ------------------------------------------------------------------

    def _generate_certificate(
        self,
        policy: dict[str, Any],
        submission: dict[str, Any],
    ) -> dict[str, Any]:
        insured = policy.get("policyholder_name") or policy.get("insured_name", "Unknown")
        policy_number = policy.get("policy_number", "N/A")
        effective = policy.get("effective_date", "")
        expiration = policy.get("expiration_date", "")
        lob = policy.get("lob", submission.get("line_of_business", "cyber"))
        coverages = policy.get("coverages", [])

        coverage_summary = []
        for cov in coverages:
            coverage_summary.append(
                {
                    "type": cov.get("coverage_name", ""),
                    "limit": cov.get("limit", 0),
                    "deductible": cov.get("deductible", 0),
                }
            )

        sections = [
            {
                "heading": "Certificate Holder",
                "content": (
                    "This certificate is issued as a matter of information only "
                    "and confers no rights upon the certificate holder."
                ),
                "data": {"certificate_holder": "As requested"},
            },
            {
                "heading": "Insured",
                "content": f"Named insured: {insured}",
                "data": {"insured_name": insured},
            },
            {
                "heading": "Coverages",
                "content": (
                    f"This is to certify that the policies of insurance listed below have been "
                    f"issued to the insured named above for the {lob.replace('_', ' ')} line of business."
                ),
                "data": {
                    "policy_number": policy_number,
                    "effective_date": effective,
                    "expiration_date": expiration,
                    "coverages": coverage_summary,
                },
            },
            {
                "heading": "Cancellation",
                "content": (
                    "Should any of the above described policies be cancelled before the "
                    "expiration date thereof, notice will be delivered in accordance with "
                    "the policy provisions."
                ),
                "data": {},
            },
        ]

        return {
            "title": f"Certificate of Insurance — {policy_number}",
            "document_type": "certificate",
            "policy_number": policy_number,
            "sections": sections,
            "effective_date": effective,
            "summary": (
                f"Certificate of Insurance for {insured}, policy {policy_number}, "
                f"covering {lob.replace('_', ' ')} from {effective} to {expiration}."
            ),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Coverage Schedule
    # ------------------------------------------------------------------

    def _generate_schedule(
        self,
        policy: dict[str, Any],
        submission: dict[str, Any],
    ) -> dict[str, Any]:
        insured = policy.get("policyholder_name") or policy.get("insured_name", "Unknown")
        policy_number = policy.get("policy_number", "N/A")
        effective = policy.get("effective_date", "")
        lob = policy.get("lob", submission.get("line_of_business", "cyber"))
        coverages = policy.get("coverages", [])

        total_limit = sum(c.get("limit", 0) for c in coverages)
        total_premium = sum(c.get("premium", 0) for c in coverages)

        schedule_rows = []
        for cov in coverages:
            schedule_rows.append(
                {
                    "coverage_code": cov.get("coverage_code", ""),
                    "coverage_name": cov.get("coverage_name", ""),
                    "limit": cov.get("limit", 0),
                    "sublimit": cov.get("sublimit"),
                    "deductible": cov.get("deductible", 0),
                    "premium": cov.get("premium", 0),
                    "waiting_period": cov.get("waiting_period"),
                    "retroactive_date": cov.get("retroactive_date"),
                }
            )

        sections = [
            {
                "heading": "Schedule of Coverages",
                "content": (
                    f"The following schedule details all coverages provided under "
                    f"{lob.replace('_', ' ').title()} policy {policy_number} issued to {insured}."
                ),
                "data": {"coverages": schedule_rows},
            },
            {
                "heading": "Aggregate Limits",
                "content": f"Total aggregate limit across all coverages: ${total_limit:,.2f}",
                "data": {
                    "total_aggregate_limit": total_limit,
                    "total_premium": total_premium,
                },
            },
            {
                "heading": "Territory & Jurisdiction",
                "content": "Coverage territory: Worldwide. Suits must be brought within the United States or Canada.",
                "data": {"territory": "Worldwide", "jurisdiction": "US/Canada"},
            },
        ]

        return {
            "title": f"Coverage Schedule — {policy_number}",
            "document_type": "schedule",
            "policy_number": policy_number,
            "sections": sections,
            "effective_date": effective,
            "summary": (
                f"Coverage schedule for policy {policy_number} issued to {insured}, "
                f"with {len(coverages)} coverages and total aggregate limit of ${total_limit:,.2f}."
            ),
            "generated_at": datetime.now(UTC).isoformat(),
        }
