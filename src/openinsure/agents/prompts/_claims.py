# mypy: ignore-errors
"""Claims agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_claims_assessment_prompt(
    claim: dict[str, Any],
    policy: dict[str, Any] | None = None,
    precedents: list[dict[str, Any]] | None = None,
) -> str:
    """Build a structured prompt for the claims assessment agent."""
    mem = _knowledge_store()
    claim_type = claim.get("claim_type", claim.get("cause_of_loss", ""))

    prompt = (
        "SYSTEM: You are the OpenInsure Claims Assessment Agent.\n"
        "You verify coverage, estimate severity, recommend reserves, and\n"
        "flag potential fraud for cyber insurance claims.\n\n"
    )

    # Claims precedent knowledge
    prec_data = mem.get_claims_precedents(claim_type)
    if prec_data:
        prompt += (
            f"CLAIMS PRECEDENTS (from knowledge base — {claim_type}):\n"
            f"- Typical reserve range: ${prec_data.get('typical_reserve_range', [0, 0])[0]:,} "
            f"- ${prec_data.get('typical_reserve_range', [0, 0])[1]:,}\n"
            f"- Average resolution: {prec_data.get('average_resolution_days', 'N/A')} days\n"
            f"- Common costs: {', '.join(prec_data.get('common_costs', []))}\n"
            f"- Red flags: {', '.join(prec_data.get('red_flags', []))}\n"
        )
        examples = prec_data.get("case_examples", [])
        if examples:
            prompt += "- Case examples:\n"
            for ex in examples:
                prompt += (
                    f"  * {ex['description']} — reserve ${ex['reserve']:,}, "
                    f"settlement ${ex['settlement']:,}, {ex['duration_days']} days\n"
                )
        prompt += "\n"

    prompt += f"CLAIM DATA:\n{json.dumps(claim, default=str, indent=2)}\n\n"

    if policy:
        prompt += f"POLICY DATA:\n{json.dumps(policy, default=str, indent=2)}\n\n"

    if precedents:
        prompt += "PRECEDENTS / SIMILAR CLAIMS:\n"
        for p in precedents:
            prompt += f"- {p.get('title', p.get('claim_type', 'N/A'))}: {p.get('summary', p.get('content', ''))}\n"
        prompt += "\n"

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "coverage_confirmed": true | false,\n'
        '  "severity_tier": "simple" | "moderate" | "complex" | "catastrophe",\n'
        '  "initial_reserve": <number>,\n'
        '  "fraud_score": <0.0-1.0>,\n'
        '  "subrogation_score": <0.0-1.0>,\n'
        '  "subrogation_basis": "explanation if third-party liability detected",\n'
        '  "coverage_analysis": "explanation of coverage determination",\n'
        '  "confidence": <0.0-1.0>,\n'
        '  "reasoning": "detailed assessment rationale"\n'
        "}\n"
    )
    return prompt
