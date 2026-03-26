# mypy: ignore-errors
"""Policy agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_policy_review_prompt(
    submission: dict[str, Any],
    underwriting_result: dict[str, Any] | None = None,
) -> str:
    """Build a structured prompt for the policy issuance review agent."""
    lob = submission.get("line_of_business", "cyber")
    mem = _knowledge_store()

    prompt = (
        "SYSTEM: You are the OpenInsure Policy Review Agent.\n"
        "You verify that coverages are appropriate, terms are complete, and\n"
        "pricing is within guidelines before policy issuance.\n\n"
    )

    # Coverage knowledge
    cov = mem.get_coverage_options(lob)
    if cov:
        prompt += "AVAILABLE COVERAGES (from knowledge base):\n"
        for c in cov:
            prompt += f"- {c['name']} (default limit ${c['default_limit']:,}): {c['description']}\n"
        prompt += "\n"

    gl = mem.get_guidelines(lob)
    if gl:
        excl = gl.get("exclusions", [])
        if excl:
            prompt += f"STANDARD EXCLUSIONS: {', '.join(excl)}\n"
        subj = gl.get("subjectivities", [])
        if subj:
            prompt += f"SUBJECTIVITIES REQUIRED: {', '.join(subj)}\n"
        prompt += "\n"

    prompt += f"SUBMISSION DATA:\n{json.dumps(submission, default=str, indent=2)}\n\n"

    if underwriting_result:
        prompt += f"UNDERWRITING RESULT:\n{json.dumps(underwriting_result, default=str, indent=2)}\n\n"

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "recommendation": "issue" | "refer" | "decline",\n'
        '  "coverage_adequate": true | false,\n'
        '  "terms_complete": true | false,\n'
        '  "pricing_within_guidelines": true | false,\n'
        '  "notes": "detailed review notes",\n'
        '  "confidence": <0.0-1.0>\n'
        "}\n"
    )
    return prompt
