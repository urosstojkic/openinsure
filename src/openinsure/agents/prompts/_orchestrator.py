# mypy: ignore-errors
"""Orchestrator agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_orchestration_prompt(
    submission: dict[str, Any],
) -> str:
    """Build a structured prompt for the workflow orchestration agent."""
    mem = _knowledge_store()

    prompt = (
        "SYSTEM: You are the OpenInsure Orchestration Agent.\n"
        "You determine the processing path, priority, and routing for\n"
        "insurance submissions and claims.\n\n"
    )

    # Workflow routing knowledge
    wf = mem.get_workflow_rules()
    routing = wf.get("routing", {})
    if routing:
        prompt += "ROUTING RULES (from knowledge base):\n"
        for path_name, path_info in routing.items():
            prompt += f"- {path_name}: {path_info.get('description', '')} → steps: {path_info.get('steps', [])}\n"
        prompt += "\n"

    authority = wf.get("authority_tiers", {})
    if authority:
        prompt += "AUTHORITY TIERS:\n"
        for tier, limits in authority.items():
            max_p = limits.get("max_premium", 0)
            max_l = limits.get("max_limit", 0)
            prompt += f"- {tier}: max premium ${max_p:,}, max limit ${max_l:,}\n"
        prompt += "\n"

    prompt += f"ENTITY DATA:\n{json.dumps(submission, default=str, indent=2)}\n\n"

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "processing_path": "standard" | "expedited" | "referral",\n'
        '  "priority": "high" | "medium" | "low",\n'
        '  "notes": "routing rationale",\n'
        '  "confidence": <0.0-1.0>\n'
        "}\n"
    )
    return prompt
