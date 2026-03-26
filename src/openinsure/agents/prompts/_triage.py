# mypy: ignore-errors
"""Triage agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _get_knowledge_context_for_lob


def build_triage_prompt(
    submission: dict[str, Any],
    guidelines: list[dict[str, Any]] | None = None,
    *,
    dynamic_knowledge: str = "",
    comparable_context: str = "",
    learning_context: str = "",
) -> str:
    """Build a structured prompt for the submission triage agent."""
    lob = submission.get("line_of_business", "cyber")
    prompt = (
        "SYSTEM: You are the OpenInsure Submission Triage Agent for cyber insurance.\n"
        "You assess whether submissions match the carrier's appetite and risk profile.\n\n"
    )

    # Historical accuracy (Feature 1)
    if learning_context:
        prompt += f"{learning_context}\n\n"

    # Underwriting guidelines from knowledge graph
    if guidelines:
        prompt += "UNDERWRITING GUIDELINES:\n"
        for g in guidelines:
            prompt += f"- {g.get('title', '')}: {g.get('content', '')}\n"
        prompt += "\n"
    else:
        # Rich knowledge-store context
        kb_ctx = _get_knowledge_context_for_lob(lob)
        if kb_ctx:
            prompt += f"UNDERWRITING GUIDELINES (from knowledge base):\n{kb_ctx}\n\n"
        else:
            prompt += (
                "UNDERWRITING GUIDELINES:\n"
                "- Appetite: IT/Tech (SIC 7xxx), Financial (SIC 6xxx), Professional Services\n"
                "- Revenue range: $500K to $50M\n"
                "- Security maturity: 4+ out of 10\n"
                "- Max prior incidents: 3\n"
                "- Required: MFA, endpoint protection\n\n"
            )

    # Dynamic industry/jurisdiction knowledge (Feature 3)
    if dynamic_knowledge:
        prompt += f"{dynamic_knowledge}\n\n"

    # Comparable accounts (Feature 2)
    if comparable_context:
        prompt += f"{comparable_context}\n\n"

    # Submission data
    prompt += f"SUBMISSION DATA:\n{json.dumps(submission, default=str, indent=2)}\n\n"

    # Output schema
    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "appetite_match": "yes" | "no" | "refer",\n'
        '  "risk_score": <1-10 integer>,\n'
        '  "risk_factors": [{"factor": "...", "impact": "positive|negative|neutral", "weight": 0.0-1.0}],\n'
        '  "recommendation": "proceed_to_quote" | "decline" | "refer",\n'
        '  "confidence": <0.0-1.0>,\n'
        '  "reasoning": "detailed explanation"\n'
        "}\n"
    )
    return prompt
