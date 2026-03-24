"""Comparable Account Retrieval — finds similar past submissions for context.

When an agent assesses a new submission, this service queries historical
submissions to find comparable accounts by industry, revenue, security
profile, and line of business.  Returns how they were priced, what happened
(claims), and the outcome — giving agents the strongest signal for pricing
and risk assessment.

Addresses issue #87.
"""

from __future__ import annotations

import statistics
from typing import Any

import structlog

from openinsure.infrastructure.factory import (
    get_claim_repository,
    get_policy_repository,
    get_submission_repository,
)

logger = structlog.get_logger(__name__)


class ComparableAccountFinder:
    """Finds similar past submissions for context."""

    def __init__(self) -> None:
        # Repos resolved lazily to avoid connection issues during import/testing
        self._sub_repo_instance = None
        self._policy_repo_instance = None
        self._claim_repo_instance = None

    @property
    def _sub_repo(self):
        if self._sub_repo_instance is None:
            self._sub_repo_instance = get_submission_repository()
        return self._sub_repo_instance

    @property
    def _policy_repo(self):
        if self._policy_repo_instance is None:
            self._policy_repo_instance = get_policy_repository()
        return self._policy_repo_instance

    @property
    def _claim_repo(self):
        if self._claim_repo_instance is None:
            self._claim_repo_instance = get_claim_repository()
        return self._claim_repo_instance

    async def find_comparables(
        self,
        submission: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find similar submissions by industry, revenue, security profile.

        Matching criteria (scored by similarity):
        - Same LOB (required)
        - Similar industry (same SIC code prefix)
        - Similar revenue band (±50%)
        - Similar employee count (±50%)
        - Similar security maturity (±2 points)

        Args:
            submission: The current submission to find comparables for.
            limit: Max number of comparables to return.

        Returns:
            List of comparable account dicts with pricing and outcome data.
        """
        # Extract current submission attributes
        lob = submission.get("line_of_business", "cyber")
        risk_data = submission.get("risk_data", {})
        cyber_data = submission.get("cyber_risk_data", {})
        if isinstance(risk_data, str):
            import json

            try:
                risk_data = json.loads(risk_data)
            except (json.JSONDecodeError, TypeError):
                risk_data = {}
        if isinstance(cyber_data, str):
            import json

            try:
                cyber_data = json.loads(cyber_data)
            except (json.JSONDecodeError, TypeError):
                cyber_data = {}
        merged = {**risk_data, **cyber_data}

        target_revenue = float(merged.get("annual_revenue", 0) or 0)
        target_employees = int(merged.get("employee_count", 0) or 0)
        target_sic = str(merged.get("industry_sic_code", merged.get("sic_code", "")))
        target_industry = str(merged.get("industry", "")).lower()
        target_security = float(merged.get("security_maturity_score", 0) or 0)
        submission_id = str(submission.get("id", ""))

        # Load all historical submissions
        all_submissions = await self._sub_repo.list_all(limit=5000)

        # Score and rank candidates
        scored: list[tuple[float, dict[str, Any]]] = []

        for candidate in all_submissions:
            cand_id = str(candidate.get("id", ""))
            if cand_id == submission_id:
                continue  # Skip self

            # Must match LOB
            if candidate.get("line_of_business", "cyber") != lob:
                continue

            # Must be past triage (have some processing history)
            status = candidate.get("status", "received")
            if status == "received":
                continue

            cand_risk = candidate.get("risk_data", {})
            cand_cyber = candidate.get("cyber_risk_data", {})
            if isinstance(cand_risk, str):
                import json

                try:
                    cand_risk = json.loads(cand_risk)
                except (json.JSONDecodeError, TypeError):
                    cand_risk = {}
            if isinstance(cand_cyber, str):
                import json

                try:
                    cand_cyber = json.loads(cand_cyber)
                except (json.JSONDecodeError, TypeError):
                    cand_cyber = {}
            cand_merged = {**cand_risk, **cand_cyber}

            score = self._similarity_score(
                target_revenue=target_revenue,
                target_employees=target_employees,
                target_sic=target_sic,
                target_industry=target_industry,
                target_security=target_security,
                cand_merged=cand_merged,
            )

            if score > 0:
                scored.append((score, candidate))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        # Enrich with policy and claims data
        results = []
        for sim_score, cand in top:
            enriched = await self._enrich_comparable(cand, sim_score)
            results.append(enriched)

        logger.info(
            "comparable_accounts.found",
            submission_id=submission_id,
            candidates_evaluated=len(all_submissions),
            matches_found=len(results),
        )
        return results

    async def get_triage_context(self, submission: dict[str, Any]) -> str:
        """Build a triage-focused comparable context string for prompt injection.

        Args:
            submission: The current submission.

        Returns:
            Multi-line string summarizing comparable triage outcomes.
        """
        comparables = await self.find_comparables(submission, limit=5)
        if not comparables:
            return ""

        proceeded = sum(1 for c in comparables if c.get("status") in ("quoted", "bound", "underwriting"))
        declined = sum(1 for c in comparables if c.get("status") == "declined")
        had_claims = sum(1 for c in comparables if c.get("claims_count", 0) > 0)

        lines = [
            f"COMPARABLE ACCOUNTS: {len(comparables)} similar submissions found.",
            f"{proceeded} proceeded to quote/bind, {declined} were declined.",
        ]
        if had_claims:
            lines.append(f"{had_claims} had subsequent claims filed.")

        for c in comparables[:3]:
            name = c.get("applicant_name", "N/A")
            status = c.get("status", "N/A")
            premium = c.get("quoted_premium")
            premium_str = f"${float(premium):,.0f}" if premium else "N/A"
            lines.append(f"- {name}: status={status}, premium={premium_str}")

        return "\n".join(lines)

    async def get_underwriting_context(self, submission: dict[str, Any]) -> str:
        """Build an underwriting-focused comparable context string.

        Args:
            submission: The current submission.

        Returns:
            Multi-line string with pricing benchmarks from comparables.
        """
        comparables = await self.find_comparables(submission, limit=5)
        if not comparables:
            return ""

        premiums = [
            float(c["quoted_premium"])
            for c in comparables
            if c.get("quoted_premium") and float(c["quoted_premium"]) > 0
        ]
        loss_ratios = [c["loss_ratio"] for c in comparables if c.get("loss_ratio") is not None]

        lines = ["COMPARABLE PRICING:"]
        if premiums:
            lines.append(
                f"Similar companies priced at ${min(premiums):,.0f}-${max(premiums):,.0f}. "
                f"Average: ${statistics.mean(premiums):,.0f}."
            )
        if loss_ratios:
            lines.append(f"Average loss ratio: {statistics.mean(loss_ratios) * 100:.0f}%")

        for c in comparables[:3]:
            name = c.get("applicant_name", "N/A")
            premium = c.get("quoted_premium")
            premium_str = f"${float(premium):,.0f}" if premium else "N/A"
            claims = c.get("claims_count", 0)
            lines.append(f"- {name}: premium={premium_str}, claims={claims}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _similarity_score(
        *,
        target_revenue: float,
        target_employees: int,
        target_sic: str,
        target_industry: str,
        target_security: float,
        cand_merged: dict[str, Any],
    ) -> float:
        """Compute a 0-1 similarity score between target and candidate."""
        score = 0.0
        weights_total = 0.0

        cand_revenue = float(cand_merged.get("annual_revenue", 0) or 0)
        cand_employees = int(cand_merged.get("employee_count", 0) or 0)
        cand_sic = str(cand_merged.get("industry_sic_code", cand_merged.get("sic_code", "")))
        cand_industry = str(cand_merged.get("industry", "")).lower()
        cand_security = float(cand_merged.get("security_maturity_score", 0) or 0)

        # Industry match (weight: 3)
        if target_sic and cand_sic:
            # Match on SIC prefix (first 2 digits = same major group)
            prefix_len = min(len(target_sic), len(cand_sic), 2)
            if target_sic[:prefix_len] == cand_sic[:prefix_len]:
                score += 3.0
                # Exact match bonus
                if target_sic[:4] == cand_sic[:4]:
                    score += 1.0
        elif target_industry and cand_industry and target_industry == cand_industry:
            score += 3.0
        weights_total += 4.0

        # Revenue match (weight: 3) — within ±50%
        if target_revenue > 0 and cand_revenue > 0:
            ratio = cand_revenue / target_revenue
            if 0.5 <= ratio <= 1.5:
                # Closer = better score (1.0 ratio = perfect)
                closeness = 1.0 - abs(1.0 - ratio) / 0.5
                score += 3.0 * closeness
        weights_total += 3.0

        # Employee count (weight: 2) — within ±50%
        if target_employees > 0 and cand_employees > 0:
            ratio = cand_employees / target_employees
            if 0.5 <= ratio <= 1.5:
                closeness = 1.0 - abs(1.0 - ratio) / 0.5
                score += 2.0 * closeness
        weights_total += 2.0

        # Security maturity (weight: 1) — within ±2 points
        if target_security > 0 and cand_security > 0:
            diff = abs(target_security - cand_security)
            if diff <= 2.0:
                score += 1.0 * (1.0 - diff / 2.0)
        weights_total += 1.0

        return score / weights_total if weights_total > 0 else 0.0

    async def _enrich_comparable(
        self,
        submission: dict[str, Any],
        similarity_score: float,
    ) -> dict[str, Any]:
        """Enrich a comparable submission with policy/claims outcome data."""
        sub_id = str(submission.get("id", ""))

        # Find associated policy
        all_policies = await self._policy_repo.list_all(limit=5000)
        related_policies = [p for p in all_policies if str(p.get("submission_id", "")) == sub_id]

        # Find claims against those policies
        claims_count = 0
        total_incurred = 0.0
        if related_policies:
            policy_ids = {str(p.get("id", "")) for p in related_policies}
            all_claims = await self._claim_repo.list_all(limit=5000)
            related_claims = [c for c in all_claims if str(c.get("policy_id", "")) in policy_ids]
            claims_count = len(related_claims)
            for c in related_claims:
                incurred = float(c.get("total_incurred", 0) or 0)
                if not incurred:
                    reserves = c.get("reserves", [])
                    payments = c.get("payments", [])
                    if isinstance(reserves, list):
                        incurred += sum(float(r.get("amount", 0)) for r in reserves)
                    if isinstance(payments, list):
                        incurred += sum(float(p.get("amount", 0)) for p in payments)
                total_incurred += incurred

        # Compute loss ratio
        quoted_premium = submission.get("quoted_premium")
        loss_ratio = None
        if quoted_premium and float(quoted_premium) > 0 and total_incurred > 0:
            loss_ratio = round(total_incurred / float(quoted_premium), 3)

        risk_data = submission.get("risk_data", {})
        if isinstance(risk_data, str):
            import json

            try:
                risk_data = json.loads(risk_data)
            except (json.JSONDecodeError, TypeError):
                risk_data = {}

        return {
            "submission_id": sub_id,
            "applicant_name": submission.get("applicant_name", submission.get("insured_name", "N/A")),
            "status": submission.get("status", "unknown"),
            "line_of_business": submission.get("line_of_business", "cyber"),
            "industry": risk_data.get("industry", "N/A"),
            "annual_revenue": risk_data.get("annual_revenue"),
            "employee_count": risk_data.get("employee_count"),
            "quoted_premium": quoted_premium,
            "claims_count": claims_count,
            "total_incurred": round(total_incurred, 2),
            "loss_ratio": loss_ratio,
            "similarity_score": round(similarity_score, 3),
        }


# Module-level singleton
_finder: ComparableAccountFinder | None = None


def get_comparable_finder() -> ComparableAccountFinder:
    """Return the singleton ComparableAccountFinder."""
    global _finder  # noqa: PLW0603
    if _finder is None:
        _finder = ComparableAccountFinder()
    return _finder
