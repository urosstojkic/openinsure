# mypy: ignore-errors
"""Billing agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_billing_prompt(policy: dict[str, Any], payment_history: list[dict[str, Any]]) -> str:
    """Build a structured prompt for the billing agent.

    Predicts payment default probability, suggests optimal installment
    schedule, and recommends collection strategy for overdue accounts.
    """
    mem = _knowledge_store()

    prompt = (
        "SYSTEM: You are the OpenInsure Billing Agent for commercial insurance.\n"
        "You analyze payment patterns, predict default risk, and recommend\n"
        "collection strategies for insurance billing accounts.\n\n"
    )

    # Billing knowledge
    billing = mem.get_billing_rules()
    terms = billing.get("payment_terms", {})
    grace = billing.get("grace_periods", {})
    escalation = billing.get("collection_escalation", {})
    if terms:
        prompt += (
            "PAYMENT TERMS (from knowledge base):\n"
            f"- Full pay discount: {terms.get('full_pay_discount', 0) * 100}%\n"
            f"- Quarterly surcharge: {terms.get('quarterly_surcharge', 0) * 100}%\n"
            f"- Monthly surcharge: {terms.get('monthly_surcharge', 0) * 100}%\n"
        )
    if grace:
        prompt += (
            f"- Standard grace period: {grace.get('standard_days', 30)} days\n"
            f"- Renewal grace period: {grace.get('renewal_days', 15)} days\n"
            f"- Reinstatement window: {grace.get('reinstatement_window_days', 60)} days\n"
        )
    if escalation:
        prompt += "COLLECTION ESCALATION:\n"
        for step, info in escalation.items():
            prompt += f"- {step}: trigger at day {info.get('trigger_days', '?')}\n"
    prompt += "\n"

    prompt += f"POLICY DATA:\n{json.dumps(policy, default=str, indent=2)}\n\n"
    prompt += f"PAYMENT HISTORY:\n{json.dumps(payment_history, default=str, indent=2)}\n\n"

    prompt += (
        "ANALYSIS GUIDELINES:\n"
        "- Assess payment default probability based on: payment timeliness, industry risk,\n"
        "  company size, claims frequency, and coverage complexity\n"
        "- Recommend installment schedule: full_pay (low risk), quarterly (medium), monthly (high)\n"
        "- For overdue accounts, recommend escalation path:\n"
        "  reminder (1-15 days) → demand (16-30 days) → cancellation notice (31-45 days) → cancel (45+ days)\n"
        "- Flag accounts needing proactive outreach\n\n"
    )

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "default_probability": <0.0-1.0>,\n'
        '  "risk_tier": "low" | "medium" | "high" | "critical",\n'
        '  "recommended_billing_plan": "full_pay" | "quarterly" | "monthly",\n'
        '  "collection_priority": "routine" | "watch" | "action_required" | "escalate",\n'
        '  "recommended_action": "none" | "reminder" | "demand_letter" |'
        ' "cancellation_notice" | "cancel_for_nonpayment",\n'
        '  "grace_period_days": <integer>,\n'
        '  "reasoning": "detailed explanation of risk assessment and recommended actions",\n'
        '  "confidence": <0.0-1.0>\n'
        "}\n"
    )
    return prompt
