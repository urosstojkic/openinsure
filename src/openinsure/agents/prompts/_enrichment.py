# mypy: ignore-errors
"""Enrichment agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_enrichment_prompt(
    submission: dict[str, Any],
    enrichment_data: dict[str, Any] | None = None,
) -> str:
    """Build a prompt for the Enrichment Agent to synthesize risk signals."""
    lob = submission.get("line_of_business", "cyber")
    mem = _knowledge_store()

    prompt = (
        "SYSTEM: You are the OpenInsure Enrichment Agent.\n"
        "You synthesize external data enrichment results into actionable risk signals\n"
        "for the underwriting team. Assess data quality and highlight key findings.\n\n"
    )

    # Data quality thresholds and risk signal definitions
    gl = mem.get_guidelines(lob)
    if gl:
        appetite = gl.get("appetite", {})
        sec_req = appetite.get("security_requirements", {})
        if sec_req:
            prompt += (
                "RISK SIGNAL DEFINITIONS (from knowledge base):\n"
                f"- Minimum security score: {sec_req.get('minimum_score', 'N/A')}\n"
                f"- Required controls: {sec_req.get('required_controls', [])}\n"
                f"- Preferred controls: {sec_req.get('preferred_controls', [])}\n"
                f"- Max prior incidents: {appetite.get('max_prior_incidents', 'N/A')}\n\n"
            )

    benchmarks = mem.get_benchmarks()
    if benchmarks:
        prompt += (
            "BENCHMARK THRESHOLDS:\n"
            f"- Target loss ratio: {benchmarks.get('target_loss_ratio', 0.60)}\n"
            f"- Target combined ratio: {benchmarks.get('target_combined_ratio', 0.90)}\n"
            f"- Hit ratio target: {benchmarks.get('hit_ratio_target', 0.25)}\n\n"
        )
    prompt += f"SUBMISSION DATA:\n{json.dumps(submission, default=str, indent=2)}\n\n"
    if enrichment_data:
        prompt += f"ENRICHMENT DATA:\n{json.dumps(enrichment_data, default=str, indent=2)}\n\n"
    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "risk_signals": [{"signal": "...", "severity": "high|medium|low", "source": "provider_name"}],\n'
        '  "composite_risk_score": <0.0-1.0>,\n'
        '  "data_quality": "high" | "medium" | "low",\n'
        '  "recommendations": ["..."],\n'
        '  "confidence": <0.0-1.0>,\n'
        '  "summary": "natural language risk context for underwriter"\n'
        "}\n"
    )
    return prompt
