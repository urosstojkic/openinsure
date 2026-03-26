# mypy: ignore-errors
"""Compliance agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_compliance_audit_prompt(
    workflow_results: dict[str, Any],
) -> str:
    """Build a structured prompt for the EU AI Act compliance audit agent."""
    mem = _knowledge_store()

    prompt = (
        "SYSTEM: You are the OpenInsure Compliance Audit Agent.\n"
        "You audit AI-driven decisions for EU AI Act compliance (Art. 12-14).\n"
        "Check transparency, explainability, human oversight, and record-keeping.\n\n"
    )

    # Compliance knowledge from store
    eu_ai = mem.get_compliance_rules("eu_ai_act")
    if eu_ai:
        articles = eu_ai.get("articles", {})
        if articles:
            prompt += "EU AI ACT REQUIREMENTS (from knowledge base):\n"
            for key, art in articles.items():
                prompt += f"- {key}: {art.get('title', '')} — {art.get('requirement', '')}\n"
            prompt += "\n"

    naic = mem.get_compliance_rules("naic_model_bulletin")
    if naic:
        prompt += f"NAIC MODEL BULLETIN: {naic.get('requirement', '')}\n\n"

    prompt += f"WORKFLOW RESULTS:\n{json.dumps(workflow_results, default=str, indent=2)}\n\n"

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "compliant": true | false,\n'
        '  "transparency_score": <0.0-1.0>,\n'
        '  "explainability_score": <0.0-1.0>,\n'
        '  "human_oversight_adequate": true | false,\n'
        '  "issues": [{"article": "Art.XX", "issue": "...", "severity": "high|medium|low"}],\n'
        '  "recommendations": ["recommendation strings"],\n'
        '  "confidence": <0.0-1.0>\n'
        "}\n"
    )
    return prompt
