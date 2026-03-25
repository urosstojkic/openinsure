# mypy: ignore-errors
"""Data enrichment service for OpenInsure.

Provides simulated external data enrichment for submissions.
Designed with a pluggable provider interface for future real API integration.
"""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()


class EnrichmentProvider:
    """Base class for enrichment data providers."""

    name: str = "base"

    async def enrich(self, submission: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class SecurityRatingProvider(EnrichmentProvider):
    """Simulated security posture rating (e.g., SecurityScorecard, BitSight)."""

    name = "security_rating"

    async def enrich(self, submission: dict[str, Any]) -> dict[str, Any]:
        seed = hashlib.md5(submission.get("id", "").encode()).hexdigest()  # noqa: S324
        rng = random.Random(seed)  # noqa: S311
        risk_data = submission.get("risk_data", {})
        has_mfa = risk_data.get("has_mfa", False)
        has_edr = risk_data.get("has_endpoint_protection", False)
        base_score = rng.randint(550, 900)
        if has_mfa:
            base_score = min(950, base_score + 50)
        if has_edr:
            base_score = min(950, base_score + 30)
        return {
            "provider": self.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "confidence": round(rng.uniform(0.7, 0.95), 2),
            "data": {
                "overall_score": base_score,
                "grade": (
                    "A" if base_score >= 800 else "B" if base_score >= 700 else "C" if base_score >= 600 else "D"
                ),
                "network_security": rng.randint(60, 100),
                "patching_cadence": rng.randint(50, 100),
                "endpoint_security": rng.randint(55, 100),
                "dns_health": rng.randint(60, 100),
                "application_security": rng.randint(50, 100),
                "ip_reputation": rng.randint(65, 100),
            },
        }


class FirmographicsProvider(EnrichmentProvider):
    """Simulated firmographic data (e.g., Dun & Bradstreet)."""

    name = "firmographics"

    async def enrich(self, submission: dict[str, Any]) -> dict[str, Any]:
        seed = hashlib.md5(submission.get("id", "").encode()).hexdigest()  # noqa: S324
        rng = random.Random(seed)  # noqa: S311
        risk_data = submission.get("risk_data", {})
        revenue = risk_data.get("annual_revenue", 5_000_000)
        employees = risk_data.get("employee_count", 50)
        sic = risk_data.get("industry_sic_code", "7372")
        industries = {
            "7372": "Software",
            "7371": "IT Services",
            "6020": "Banking",
            "6311": "Insurance",
            "8011": "Healthcare",
            "8742": "Consulting",
        }
        return {
            "provider": self.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "confidence": round(rng.uniform(0.75, 0.95), 2),
            "data": {
                "verified_revenue": revenue * rng.uniform(0.85, 1.15),
                "verified_employee_count": max(1, int(employees * rng.uniform(0.9, 1.1))),
                "industry_description": industries.get(str(sic)[:4], "Technology"),
                "sic_code": str(sic),
                "years_in_business": rng.randint(2, 30),
                "duns_number": f"D{rng.randint(100000000, 999999999)}",
                "credit_rating": rng.choice(["AAA", "AA", "A", "BBB", "BB"]),
                "public_company": rng.random() < 0.2,
            },
        }


class BreachHistoryProvider(EnrichmentProvider):
    """Simulated breach history lookup (e.g., Have I Been Pwned / dark web monitoring)."""

    name = "breach_history"

    async def enrich(self, submission: dict[str, Any]) -> dict[str, Any]:
        seed = hashlib.md5(submission.get("id", "").encode()).hexdigest()  # noqa: S324
        rng = random.Random(seed)  # noqa: S311
        risk_data = submission.get("risk_data", {})
        prior = risk_data.get("prior_incidents", 0)
        breach_count = prior + (1 if rng.random() < 0.15 else 0)
        breaches = []
        for _i in range(min(breach_count, 3)):
            year = 2024 - rng.randint(0, 4)
            breaches.append(
                {
                    "year": year,
                    "type": rng.choice(["data_breach", "ransomware", "phishing", "credential_theft"]),
                    "records_affected": rng.randint(100, 500_000),
                    "publicly_disclosed": rng.random() < 0.6,
                }
            )
        return {
            "provider": self.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "confidence": round(rng.uniform(0.6, 0.9), 2),
            "data": {
                "total_known_breaches": breach_count,
                "breaches": breaches,
                "dark_web_mentions": rng.randint(0, 5),
                "credential_exposures": rng.randint(0, 200),
            },
        }


# Default provider registry
_PROVIDERS: list[EnrichmentProvider] = [
    SecurityRatingProvider(),
    FirmographicsProvider(),
    BreachHistoryProvider(),
]


async def enrich_submission(submission: dict[str, Any]) -> dict[str, Any]:
    """Run all enrichment providers against a submission.

    Returns a dict with provider results and a synthesized risk summary.
    """
    results: dict[str, Any] = {}
    for provider in _PROVIDERS:
        try:
            result = await provider.enrich(submission)
            results[provider.name] = result
        except Exception:
            logger.warning("enrichment.provider_failed", provider=provider.name, exc_info=True)
            results[provider.name] = {"provider": provider.name, "error": "provider_unavailable"}

    # Synthesize risk summary
    sec_data = results.get("security_rating", {}).get("data", {})
    firm_data = results.get("firmographics", {}).get("data", {})
    breach_data = results.get("breach_history", {}).get("data", {})

    sec_score = sec_data.get("overall_score", 700)
    breach_count = breach_data.get("total_known_breaches", 0)
    credit = firm_data.get("credit_rating", "BB")
    credit_scores = {"AAA": 1.0, "AA": 0.85, "A": 0.7, "BBB": 0.55, "BB": 0.4, "B": 0.25}

    risk_score = round(
        (sec_score / 950) * 0.4 + credit_scores.get(credit, 0.4) * 0.3 + max(0, 1 - breach_count * 0.2) * 0.3,
        3,
    )

    return {
        "enrichment_data": results,
        "risk_summary": {
            "composite_risk_score": risk_score,
            "security_grade": sec_data.get("grade", "N/A"),
            "verified_revenue": firm_data.get("verified_revenue"),
            "breach_count": breach_count,
            "credit_rating": credit,
            "enriched_at": datetime.now(UTC).isoformat(),
        },
    }
