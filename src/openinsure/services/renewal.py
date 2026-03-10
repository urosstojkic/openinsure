"""Renewal processing service."""

from datetime import date, timedelta
from typing import Any

from openinsure.infrastructure.factory import get_policy_repository


async def identify_renewals(days_ahead: int = 90) -> list[dict[str, Any]]:
    """Find policies approaching renewal within *days_ahead* days."""
    repo = get_policy_repository()
    policies = await repo.list_all(limit=500)
    target_date = date.today() + timedelta(days=days_ahead)
    renewals: list[dict[str, Any]] = []
    for p in policies:
        exp = p.get("expiration_date")
        if exp and str(exp) <= str(target_date):
            days_to_expiry = (date.fromisoformat(str(exp)) - date.today()).days if exp else 0
            renewals.append({**p, "days_to_expiry": days_to_expiry})
    return sorted(renewals, key=lambda x: x.get("days_to_expiry", 999))


async def generate_renewal_terms(policy: dict[str, Any]) -> dict[str, Any]:
    """Generate renewal terms from an existing policy."""
    original_premium = float(policy.get("total_premium", 0) or policy.get("premium", 0))
    return {
        "original_policy": policy.get("policy_number"),
        "renewal_premium": original_premium * 1.05,  # 5% increase
        "effective_date": policy.get("expiration_date"),
        "changes": [],
        "recommendation": ("renew_as_is" if original_premium > 0 else "review_required"),
    }
