# mypy: ignore-errors
"""Underwriting agent prompt builder and rating engine helper."""

from __future__ import annotations

import json
from typing import Any

import structlog

from openinsure.agents.prompts._knowledge import _get_knowledge_context_for_lob

logger = structlog.get_logger()


def build_underwriting_prompt(
    submission: dict[str, Any],
    triage_result: dict[str, Any] | None = None,
    guidelines: list[dict[str, Any]] | None = None,
    rating_breakdown: dict[str, Any] | None = None,
    *,
    dynamic_knowledge: str = "",
    comparable_context: str = "",
    learning_context: str = "",
) -> str:
    """Build a structured prompt for the underwriting / pricing agent."""
    lob = submission.get("line_of_business", "cyber")
    prompt = (
        "SYSTEM: You are the OpenInsure Underwriting Agent for cyber insurance.\n"
        "You assess risk and calculate premium pricing.\n\n"
    )

    # Historical accuracy (Feature 1)
    if learning_context:
        prompt += f"{learning_context}\n\n"

    if guidelines:
        prompt += "UNDERWRITING GUIDELINES:\n"
        for g in guidelines:
            prompt += f"- {g.get('title', '')}: {g.get('content', '')}\n"
        prompt += "\n"
    else:
        kb_ctx = _get_knowledge_context_for_lob(lob)
        if kb_ctx:
            prompt += f"PRICING GUIDELINES (from knowledge base):\n{kb_ctx}\n\n"
        else:
            prompt += (
                "PRICING GUIDELINES:\n"
                "- Base rate: $1.50 per $1,000 revenue\n"
                "- Adjust for: industry SIC code, security maturity, prior incidents\n"
                "- Min premium: $2,500 | Max premium: $500,000\n"
                "- Security controls (MFA, endpoint, backup, IR plan) earn credits\n"
                "- Prior incidents: 1 → 1.25x, 2 → 1.5x, 3+ → 2.0x\n\n"
            )

    # Dynamic industry/jurisdiction knowledge (Feature 3)
    if dynamic_knowledge:
        prompt += f"{dynamic_knowledge}\n\n"

    # Comparable pricing (Feature 2)
    if comparable_context:
        prompt += f"{comparable_context}\n\n"

    prompt += f"SUBMISSION DATA:\n{json.dumps(submission, default=str, indent=2)}\n\n"

    if triage_result:
        prompt += f"TRIAGE RESULT:\n{json.dumps(triage_result, default=str, indent=2)}\n\n"

    if rating_breakdown:
        prompt += f"RATING ENGINE BREAKDOWN:\n{json.dumps(rating_breakdown, default=str, indent=2)}\n\n"

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "risk_score": <1-100 integer>,\n'
        '  "recommended_premium": <number>,\n'
        '  "rating_factors": {"factor_name": <multiplier>, ...},\n'
        '  "conditions": ["special conditions or exclusions"],\n'
        '  "confidence": <0.0-1.0>,\n'
        '  "reasoning": "detailed explanation of pricing rationale"\n'
        "}\n"
    )
    return prompt


# ---------------------------------------------------------------------------
# Rating engine helper (for #70 — rating breakdown in underwriting prompt)
# ---------------------------------------------------------------------------


def _get_rating_breakdown(submission: dict[str, Any]) -> dict[str, Any] | None:
    """Run the deterministic rating engine and return the factor breakdown.

    Returns ``None`` when the submission lacks enough data to rate.
    """
    try:
        from decimal import Decimal

        from openinsure.services.rating import CyberRatingEngine, RatingInput

        risk_data = submission.get("risk_data", {})
        if isinstance(risk_data, str):
            risk_data = json.loads(risk_data)

        cyber_data = submission.get("cyber_risk_data", {})
        if isinstance(cyber_data, str):
            cyber_data = json.loads(cyber_data)

        merged = {**risk_data, **cyber_data}

        revenue = merged.get("annual_revenue", 0)
        if not revenue:
            return None

        ri = RatingInput(
            annual_revenue=Decimal(str(revenue)),
            employee_count=int(merged.get("employee_count", 1) or 1),
            industry_sic_code=str(merged.get("industry_sic_code", merged.get("sic_code", "7372"))),
            security_maturity_score=float(merged.get("security_maturity_score", 5.0) or 5.0),
            has_mfa=bool(merged.get("has_mfa", False)),
            has_endpoint_protection=bool(merged.get("has_endpoint_protection", False)),
            has_backup_strategy=bool(merged.get("has_backup_strategy", False)),
            has_incident_response_plan=bool(merged.get("has_incident_response_plan", False)),
            prior_incidents=int(merged.get("prior_incidents", 0) or 0),
            requested_limit=Decimal(str(merged.get("requested_limit", 1000000))),
            requested_deductible=Decimal(str(merged.get("requested_deductible", 10000))),
        )
        engine = CyberRatingEngine()
        result = engine.calculate_premium(ri)
        return {
            "base_premium": str(result.base_premium),
            "adjusted_premium": str(result.adjusted_premium),
            "final_premium": str(result.final_premium),
            "factors_applied": {k: str(v) for k, v in result.factors_applied.items()},
            "confidence": result.confidence,
            "explanation": result.explanation,
            "warnings": result.warnings,
        }
    except Exception:
        logger.debug("prompts.rating_breakdown_failed", exc_info=True)
        return None
