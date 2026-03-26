# mypy: ignore-errors
"""Structured prompt builders for OpenInsure Foundry agents.

Each builder assembles a complete prompt with:
  - System context (agent role, authority)
  - Underwriting guidelines (from knowledge graph or defaults)
  - Entity data (submission, claim, policy)
  - Output schema (JSON format the agent must return)

All 10 agents query the in-memory knowledge store before reasoning,
making it the core competitive advantage of the platform.

Dynamic knowledge retrieval (Feature 3) ensures each submission receives
contextual knowledge based on industry, jurisdiction, and risk profile.
Comparable account context (Feature 2) and historical accuracy data
(Feature 1) are injected into triage and underwriting prompts.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Re-export all public and semi-public symbols so that existing imports
# like ``from openinsure.agents.prompts import build_prompt_for_step``
# continue to work unchanged.
# ---------------------------------------------------------------------------
from openinsure.agents.prompts._billing import build_billing_prompt as build_billing_prompt
from openinsure.agents.prompts._claims import (
    build_claims_assessment_prompt as build_claims_assessment_prompt,
)
from openinsure.agents.prompts._comparable import (
    _get_comparable_triage_context as _get_comparable_triage_context,
)
from openinsure.agents.prompts._comparable import (
    _get_comparable_underwriting_context as _get_comparable_underwriting_context,
)
from openinsure.agents.prompts._compliance import (
    build_compliance_audit_prompt as build_compliance_audit_prompt,
)
from openinsure.agents.prompts._document import build_document_prompt as build_document_prompt
from openinsure.agents.prompts._enrichment import build_enrichment_prompt as build_enrichment_prompt
from openinsure.agents.prompts._knowledge import (
    _estimate_primary_risk as _estimate_primary_risk,
)
from openinsure.agents.prompts._knowledge import (
    _extract_industry as _extract_industry,
)
from openinsure.agents.prompts._knowledge import (
    _format_dynamic_knowledge as _format_dynamic_knowledge,
)
from openinsure.agents.prompts._knowledge import (
    _get_knowledge_context_for_lob as _get_knowledge_context_for_lob,
)
from openinsure.agents.prompts._knowledge import (
    _get_learning_context as _get_learning_context,
)
from openinsure.agents.prompts._knowledge import (
    _incidents_match_tier as _incidents_match_tier,
)
from openinsure.agents.prompts._knowledge import (
    _knowledge_store as _knowledge_store,
)
from openinsure.agents.prompts._knowledge import (
    _parse_tier_value as _parse_tier_value,
)
from openinsure.agents.prompts._knowledge import (
    _retrieve_relevant_knowledge as _retrieve_relevant_knowledge,
)
from openinsure.agents.prompts._knowledge import (
    _revenue_matches_tier as _revenue_matches_tier,
)
from openinsure.agents.prompts._knowledge import (
    _score_matches_tier as _score_matches_tier,
)
from openinsure.agents.prompts._knowledge import (
    _static_guidelines as _static_guidelines,
)
from openinsure.agents.prompts._knowledge import (
    _submission_specific_guidelines as _submission_specific_guidelines,
)
from openinsure.agents.prompts._knowledge import (
    get_claims_context as get_claims_context,
)
from openinsure.agents.prompts._knowledge import (
    get_product_context as get_product_context,
)
from openinsure.agents.prompts._knowledge import (
    get_triage_context as get_triage_context,
)
from openinsure.agents.prompts._orchestrator import (
    build_orchestration_prompt as build_orchestration_prompt,
)
from openinsure.agents.prompts._policy import (
    build_policy_review_prompt as build_policy_review_prompt,
)
from openinsure.agents.prompts._triage import build_triage_prompt as build_triage_prompt
from openinsure.agents.prompts._underwriting import (
    _get_rating_breakdown as _get_rating_breakdown,
)
from openinsure.agents.prompts._underwriting import (
    build_underwriting_prompt as build_underwriting_prompt,
)

__all__ = [
    "build_billing_prompt",
    "build_claims_assessment_prompt",
    "build_compliance_audit_prompt",
    "build_document_prompt",
    "build_enrichment_prompt",
    "build_orchestration_prompt",
    "build_policy_review_prompt",
    "build_prompt_for_step",
    "build_triage_prompt",
    "build_underwriting_prompt",
    "get_claims_context",
    "get_product_context",
    "get_triage_context",
]


# ---------------------------------------------------------------------------
# Unified dispatcher used by workflow_engine
# ---------------------------------------------------------------------------


async def build_prompt_for_step(
    step_name: str,
    context: dict[str, Any],
    entity_id: str,
    entity_type: str,
) -> str:
    """Build the appropriate structured prompt based on the workflow step name.

    This is the single entry-point called by the workflow engine.  It
    selects the correct builder, enriches the prompt with knowledge-graph
    context, and returns the assembled prompt string.
    """
    entity_data = context.get("entity_data", {})

    if step_name == "orchestration":
        return build_orchestration_prompt(entity_data)

    if step_name == "enrichment":
        enrichment_data = context.get("enrichment_result")
        return build_enrichment_prompt(entity_data, enrichment_data=enrichment_data)

    if step_name == "intake":
        guidelines = await get_triage_context(entity_data)
        # Feature 1+2+3: Inject learning context, comparables, and dynamic knowledge
        learning_ctx = await _get_learning_context("triage")
        comparable_ctx = await _get_comparable_triage_context(entity_data)
        knowledge = await _retrieve_relevant_knowledge(entity_data)
        dynamic_kb = _format_dynamic_knowledge(knowledge)
        return build_triage_prompt(
            entity_data,
            guidelines=guidelines or None,
            dynamic_knowledge=dynamic_kb,
            comparable_context=comparable_ctx,
            learning_context=learning_ctx,
        )

    if step_name == "underwriting":
        triage_result = context.get("intake_result")
        guidelines = await get_triage_context(entity_data)
        rating_breakdown = _get_rating_breakdown(entity_data)
        # Feature 1+2+3: Inject learning context, comparables, and dynamic knowledge
        learning_ctx = await _get_learning_context("underwriting")
        comparable_ctx = await _get_comparable_underwriting_context(entity_data)
        knowledge = await _retrieve_relevant_knowledge(entity_data)
        dynamic_kb = _format_dynamic_knowledge(knowledge)
        return build_underwriting_prompt(
            entity_data,
            triage_result=triage_result,
            guidelines=guidelines or None,
            rating_breakdown=rating_breakdown,
            dynamic_knowledge=dynamic_kb,
            comparable_context=comparable_ctx,
            learning_context=learning_ctx,
        )

    if step_name == "policy_review":
        uw_result = context.get("underwriting_result")
        return build_policy_review_prompt(entity_data, underwriting_result=uw_result)

    if step_name == "assessment":
        # Claims assessment or renewal assessment
        if entity_type == "claim":
            precedents = await get_claims_context(entity_data)
            return build_claims_assessment_prompt(entity_data, precedents=precedents or None)
        # Renewal — reuse underwriting prompt
        return build_underwriting_prompt(entity_data)

    if step_name == "compliance":
        # Gather all step results into a single dict for auditing
        workflow_results = {key: val for key, val in context.items() if key.endswith("_result")}
        return build_compliance_audit_prompt(workflow_results)

    # Fallback — generic prompt
    return (
        f"SYSTEM: You are an OpenInsure agent processing step '{step_name}'.\n"
        f"Entity: {entity_type}/{entity_id}\n"
        f"Context: {json.dumps(entity_data, default=str)[:2000]}\n"
        "Respond with JSON.\n"
    )
