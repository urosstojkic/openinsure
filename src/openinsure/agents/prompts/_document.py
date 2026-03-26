# mypy: ignore-errors
"""Document agent prompt builder."""

from __future__ import annotations

import json
from typing import Any

from openinsure.agents.prompts._knowledge import _knowledge_store


def build_document_prompt(policy: dict[str, Any], submission: dict[str, Any], doc_type: str) -> str:
    """Build a structured prompt for the document generation agent.

    Generates policy document content — executive summary, coverage
    descriptions, conditions, and exclusions — in natural insurance language.
    """
    lob = submission.get("line_of_business", policy.get("line_of_business", "cyber"))
    mem = _knowledge_store()

    prompt = (
        "SYSTEM: You are the OpenInsure Document Generation Agent.\n"
        "You produce professional insurance document content including declarations pages,\n"
        "certificates of insurance, and coverage schedules.\n"
        "Write in clear, formal insurance language suitable for policyholders and brokers.\n\n"
    )

    # Coverage knowledge for document generation
    cov = mem.get_coverage_options(lob)
    if cov:
        prompt += "STANDARD COVERAGES (from knowledge base):\n"
        for c in cov:
            prompt += f"- {c['name']}: {c['description']} (default limit ${c['default_limit']:,})\n"
        prompt += "\n"

    gl = mem.get_guidelines(lob)
    if gl:
        excl = gl.get("exclusions", [])
        if excl:
            prompt += f"STANDARD EXCLUSIONS: {', '.join(excl)}\n\n"

    prompt += f"DOCUMENT TYPE: {doc_type}\n\n"
    prompt += f"POLICY DATA:\n{json.dumps(policy, default=str, indent=2)}\n\n"
    prompt += f"SUBMISSION DATA:\n{json.dumps(submission, default=str, indent=2)}\n\n"

    if doc_type == "declaration":
        prompt += (
            "Generate a declarations page including:\n"
            "- Named insured and policy number\n"
            "- Policy period (effective and expiration dates)\n"
            "- Coverage summary with limits and deductibles\n"
            "- Premium breakdown by coverage\n"
            "- Agent/broker information\n"
            "- Special conditions or endorsements\n\n"
        )
    elif doc_type == "certificate":
        prompt += (
            "Generate a Certificate of Insurance including:\n"
            "- Certificate holder information\n"
            "- Insured name and address\n"
            "- Policy number and period\n"
            "- Coverage types and limits\n"
            "- Description of operations\n"
            "- Cancellation notice provisions\n\n"
        )
    elif doc_type == "schedule":
        prompt += (
            "Generate a Coverage Schedule including:\n"
            "- Detailed coverage listing with codes\n"
            "- Per-coverage limits, sublimits, and deductibles\n"
            "- Aggregate limits\n"
            "- Coverage territory and jurisdiction\n"
            "- Retroactive dates where applicable\n"
            "- Coverage conditions and waiting periods\n\n"
        )

    prompt += (
        "RESPOND WITH JSON ONLY:\n"
        "{\n"
        '  "title": "Document title",\n'
        '  "document_type": "declaration" | "certificate" | "schedule",\n'
        '  "sections": [\n'
        "    {\n"
        '      "heading": "Section title",\n'
        '      "content": "Section body text in professional insurance language",\n'
        '      "data": {<optional structured data for tables/grids>}\n'
        "    }\n"
        "  ],\n"
        '  "effective_date": "YYYY-MM-DD",\n'
        '  "summary": "One-paragraph executive summary",\n'
        '  "confidence": <0.0-1.0>\n'
        "}\n"
    )
    return prompt
