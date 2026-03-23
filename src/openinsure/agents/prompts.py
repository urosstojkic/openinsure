"""Structured prompt builders for OpenInsure Foundry agents.

Each builder assembles a complete prompt with:
  - System context (agent role, authority)
  - Underwriting guidelines (from knowledge graph or defaults)
  - Entity data (submission, claim, policy)
  - Output schema (JSON format the agent must return)

Addresses #67: Wire Foundry agents with structured prompts and knowledge retrieval.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Knowledge retrieval helpers
# ---------------------------------------------------------------------------


async def get_triage_context(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieve underwriting guidelines relevant to this submission."""
    try:
        from openinsure.infrastructure.factory import get_knowledge_store

        store = get_knowledge_store()
        if store is not None:
            lob = submission.get("line_of_business", "cyber")
            guidelines = await store.query(f"underwriting_guidelines_{lob}")
            if isinstance(guidelines, list) and guidelines:
                return guidelines
    except Exception:
        logger.debug("prompts.knowledge_retrieval_failed", exc_info=True)

    # Fall back to static knowledge from KnowledgeAgent
    return _static_guidelines(submission)


async def get_claims_context(claim: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieve precedents and coverage rules relevant to this claim."""
    try:
        from openinsure.infrastructure.factory import get_knowledge_store

        store = get_knowledge_store()
        if store is not None:
            claim_type = claim.get("claim_type", "cyber_incident")
            precedents = await store.query(f"claims_precedents_{claim_type}")
            if isinstance(precedents, list) and precedents:
                return precedents
    except Exception:
        logger.debug("prompts.claims_knowledge_failed", exc_info=True)
    return []


def _static_guidelines(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Return built-in underwriting guidelines when the knowledge store is unavailable."""
    lob = submission.get("line_of_business", "cyber")
    try:
        from openinsure.agents.knowledge_agent import UNDERWRITING_GUIDELINES

        if lob in UNDERWRITING_GUIDELINES:
            raw = UNDERWRITING_GUIDELINES[lob]
            return [{"title": f"{lob.title()} Guidelines", "content": json.dumps(raw, default=str)}]
    except Exception:
        logger.debug("prompts.static_guidelines_failed", exc_info=True)
    return []


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_triage_prompt(
    submission: dict[str, Any],
    guidelines: list[dict[str, Any]] | None = None,
) -> str:
    """Build a structured prompt for the submission triage agent."""
    prompt = (
        "SYSTEM: You are the OpenInsure Submission Triage Agent for cyber insurance.\n"
        "You assess whether submissions match the carrier's appetite and risk profile.\n\n"
    )

    # Underwriting guidelines from knowledge graph
    if guidelines:
        prompt += "UNDERWRITING GUIDELINES:\n"
        for g in guidelines:
            prompt += f"- {g.get('title', '')}: {g.get('content', '')}\n"
        prompt += "\n"
    else:
        prompt += (
            "UNDERWRITING GUIDELINES:\n"
            "- Appetite: IT/Tech (SIC 7xxx), Financial (SIC 6xxx), Professional Services\n"
            "- Revenue range: $500K to $50M\n"
            "- Security maturity: 4+ out of 10\n"
            "- Max prior incidents: 3\n"
            "- Required: MFA, endpoint protection\n\n"
        )

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


def build_underwriting_prompt(
    submission: dict[str, Any],
    triage_result: dict[str, Any] | None = None,
    guidelines: list[dict[str, Any]] | None = None,
    rating_breakdown: dict[str, Any] | None = None,
) -> str:
    """Build a structured prompt for the underwriting / pricing agent."""
    prompt = (
        "SYSTEM: You are the OpenInsure Underwriting Agent for cyber insurance.\n"
        "You assess risk and calculate premium pricing.\n\n"
    )

    if guidelines:
        prompt += "UNDERWRITING GUIDELINES:\n"
        for g in guidelines:
            prompt += f"- {g.get('title', '')}: {g.get('content', '')}\n"
        prompt += "\n"
    else:
        prompt += (
            "PRICING GUIDELINES:\n"
            "- Base rate: $1.50 per $1,000 revenue\n"
            "- Adjust for: industry SIC code, security maturity, prior incidents\n"
            "- Min premium: $2,500 | Max premium: $500,000\n"
            "- Security controls (MFA, endpoint, backup, IR plan) earn credits\n"
            "- Prior incidents: 1 → 1.25x, 2 → 1.5x, 3+ → 2.0x\n\n"
        )

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


def build_policy_review_prompt(
    submission: dict[str, Any],
    underwriting_result: dict[str, Any] | None = None,
) -> str:
    """Build a structured prompt for the policy issuance review agent."""
    prompt = (
        "SYSTEM: You are the OpenInsure Policy Review Agent.\n"
        "You verify that coverages are appropriate, terms are complete, and\n"
        "pricing is within guidelines before policy issuance.\n\n"
    )

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


def build_claims_assessment_prompt(
    claim: dict[str, Any],
    policy: dict[str, Any] | None = None,
    precedents: list[dict[str, Any]] | None = None,
) -> str:
    """Build a structured prompt for the claims assessment agent."""
    prompt = (
        "SYSTEM: You are the OpenInsure Claims Assessment Agent.\n"
        "You verify coverage, estimate severity, recommend reserves, and\n"
        "flag potential fraud for cyber insurance claims.\n\n"
    )

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


def build_compliance_audit_prompt(
    workflow_results: dict[str, Any],
) -> str:
    """Build a structured prompt for the EU AI Act compliance audit agent."""
    prompt = (
        "SYSTEM: You are the OpenInsure Compliance Audit Agent.\n"
        "You audit AI-driven decisions for EU AI Act compliance (Art. 12-14).\n"
        "Check transparency, explainability, human oversight, and record-keeping.\n\n"
    )

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


def build_orchestration_prompt(
    submission: dict[str, Any],
) -> str:
    """Build a structured prompt for the workflow orchestration agent."""
    prompt = (
        "SYSTEM: You are the OpenInsure Orchestration Agent.\n"
        "You determine the processing path, priority, and routing for\n"
        "insurance submissions and claims.\n\n"
    )

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


# ---------------------------------------------------------------------------
# Billing prompt builder (#77)
# ---------------------------------------------------------------------------


def build_billing_prompt(policy: dict[str, Any], payment_history: list[dict[str, Any]]) -> str:
    """Build a structured prompt for the billing agent.

    Predicts payment default probability, suggests optimal installment
    schedule, and recommends collection strategy for overdue accounts.
    """
    prompt = (
        "SYSTEM: You are the OpenInsure Billing Agent for commercial insurance.\n"
        "You analyze payment patterns, predict default risk, and recommend\n"
        "collection strategies for insurance billing accounts.\n\n"
    )

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


# ---------------------------------------------------------------------------
# Document prompt builder (#78)
# ---------------------------------------------------------------------------


def build_document_prompt(policy: dict[str, Any], submission: dict[str, Any], doc_type: str) -> str:
    """Build a structured prompt for the document generation agent.

    Generates policy document content — executive summary, coverage
    descriptions, conditions, and exclusions — in natural insurance language.
    """
    prompt = (
        "SYSTEM: You are the OpenInsure Document Generation Agent.\n"
        "You produce professional insurance document content including declarations pages,\n"
        "certificates of insurance, and coverage schedules.\n"
        "Write in clear, formal insurance language suitable for policyholders and brokers.\n\n"
    )

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


def build_enrichment_prompt(
    submission: dict[str, Any],
    enrichment_data: dict[str, Any] | None = None,
) -> str:
    """Build a prompt for the Enrichment Agent to synthesize risk signals."""
    prompt = (
        "SYSTEM: You are the OpenInsure Enrichment Agent.\n"
        "You synthesize external data enrichment results into actionable risk signals\n"
        "for the underwriting team. Assess data quality and highlight key findings.\n\n"
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
        return build_triage_prompt(entity_data, guidelines=guidelines or None)

    if step_name == "underwriting":
        triage_result = context.get("intake_result")
        guidelines = await get_triage_context(entity_data)
        rating_breakdown = _get_rating_breakdown(entity_data)
        return build_underwriting_prompt(
            entity_data,
            triage_result=triage_result,
            guidelines=guidelines or None,
            rating_breakdown=rating_breakdown,
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
