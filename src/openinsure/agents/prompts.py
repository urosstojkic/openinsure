"""Structured prompt builders for OpenInsure Foundry agents.

Each builder assembles a complete prompt with:
  - System context (agent role, authority)
  - Underwriting guidelines (from knowledge graph or defaults)
  - Entity data (submission, claim, policy)
  - Output schema (JSON format the agent must return)

All 10 agents query the in-memory knowledge store before reasoning,
making it the core competitive advantage of the platform.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Knowledge retrieval helpers
# ---------------------------------------------------------------------------


def _knowledge_store():
    """Return the always-available in-memory knowledge store."""
    from openinsure.infrastructure.knowledge_store import get_knowledge_store

    return get_knowledge_store()


async def get_triage_context(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieve underwriting guidelines relevant to this submission.

    Returns guidelines filtered by LOB, industry, and risk profile so that
    different submissions receive different knowledge context.
    """
    # Try Cosmos DB first
    try:
        from openinsure.infrastructure.factory import get_knowledge_store as get_cosmos

        store = get_cosmos()
        if store is not None:
            lob = submission.get("line_of_business", "cyber")
            guidelines = await store.query(f"underwriting_guidelines_{lob}")
            if isinstance(guidelines, list) and guidelines:
                return guidelines
    except Exception:
        logger.debug("prompts.knowledge_retrieval_failed", exc_info=True)

    # Fall back to rich in-memory knowledge store with submission-specific filtering
    return _submission_specific_guidelines(submission)


async def get_claims_context(claim: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieve precedents and coverage rules relevant to this claim."""
    # Try Cosmos DB first
    try:
        from openinsure.infrastructure.factory import get_knowledge_store as get_cosmos

        store = get_cosmos()
        if store is not None:
            claim_type = claim.get("claim_type", "cyber_incident")
            precedents = await store.query(f"claims_precedents_{claim_type}")
            if isinstance(precedents, list) and precedents:
                return precedents
    except Exception:
        logger.debug("prompts.claims_knowledge_failed", exc_info=True)

    # Fall back to rich in-memory knowledge store
    mem = _knowledge_store()
    claim_type = claim.get("claim_type", claim.get("cause_of_loss", ""))
    precedent = mem.get_claims_precedents(claim_type)
    if precedent:
        return [{"title": f"{claim_type.title()} Precedents", "content": json.dumps(precedent, default=str)}]
    return []


def _static_guidelines(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Return built-in underwriting guidelines from the in-memory knowledge store."""
    lob = submission.get("line_of_business", "cyber")
    mem = _knowledge_store()
    gl = mem.get_guidelines(lob)
    if gl:
        return [{"title": f"{lob.title()} Guidelines", "content": json.dumps(gl, default=str)}]
    return []


def _submission_specific_guidelines(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Return guidelines filtered by the submission's LOB, industry, and risk profile.

    Unlike ``_static_guidelines`` which returns the entire LOB guideline blob,
    this function extracts only the factors relevant to the specific submission
    so that a healthcare company and a tech company receive different knowledge.
    """
    lob = submission.get("line_of_business", "cyber")
    mem = _knowledge_store()
    gl = mem.get_guidelines(lob)
    if not gl:
        return []

    results: list[dict[str, Any]] = []

    # Always include the base LOB guidelines
    results.append({"title": f"{lob.title()} Guidelines", "content": json.dumps(gl, default=str)})

    # Extract submission attributes for filtering
    risk_data = submission.get("risk_data", {})
    cyber_data = submission.get("cyber_risk_data", {})
    if isinstance(risk_data, str):
        try:
            risk_data = json.loads(risk_data)
        except (json.JSONDecodeError, TypeError):
            risk_data = {}
    if isinstance(cyber_data, str):
        try:
            cyber_data = json.loads(cyber_data)
        except (json.JSONDecodeError, TypeError):
            cyber_data = {}
    merged = {**risk_data, **cyber_data}

    industry = merged.get("industry", "").lower().replace(" ", "_")
    sic_code = str(merged.get("industry_sic_code", merged.get("sic_code", "")))
    revenue = merged.get("annual_revenue", 0) or 0
    security_score = merged.get("security_maturity_score", 0) or 0
    prior_incidents = merged.get("prior_incidents", 0) or 0

    # Industry-specific rating factor
    rf = gl.get("rating_factors", {})
    industry_factors = rf.get("industry_factors", {})
    matched_industry_factor = industry_factors.get(industry)
    if matched_industry_factor is not None:
        results.append({
            "title": f"Industry Factor: {industry}",
            "content": (
                f"Industry '{industry}' has a rating factor of {matched_industry_factor}. "
                f"{'This is a favorable rate (below 1.0).' if matched_industry_factor < 1.0 else ''}"
                f"{'This is an elevated rate (above 1.0) — increased scrutiny required.' if matched_industry_factor > 1.0 else ''}"
            ),
        })
    elif industry:
        results.append({
            "title": f"Industry Factor: {industry}",
            "content": (
                f"Industry '{industry}' is not in the standard rating table. "
                "Apply default factor of 1.0 and flag for underwriter review."
            ),
        })

    # SIC code appetite check
    appetite = gl.get("appetite", {})
    sic_codes = appetite.get("sic_codes", {})
    if sic_code:
        sic_status = "unknown"
        for category, ranges in sic_codes.items():
            for r in ranges:
                if "-" in r:
                    low, high = r.split("-")
                    if low.strip().isdigit() and high.strip().isdigit():
                        if int(low.strip()) <= int(sic_code[:4] if len(sic_code) >= 4 else sic_code) <= int(high.strip()):
                            sic_status = category
                            break
        results.append({
            "title": f"SIC Code {sic_code} Classification",
            "content": (
                f"SIC code {sic_code} is classified as '{sic_status}' for this LOB. "
                f"{'WITHIN APPETITE — proceed normally.' if sic_status == 'preferred' else ''}"
                f"{'ACCEPTABLE — standard processing.' if sic_status == 'acceptable' else ''}"
                f"{'DECLINED CLASS — do not proceed.' if sic_status == 'declined' else ''}"
                f"{'NOT CLASSIFIED — refer to underwriter.' if sic_status == 'unknown' else ''}"
            ),
        })

    # Revenue tier context
    rev_range = appetite.get("revenue_range", {})
    min_rev = rev_range.get("min", 0)
    max_rev = rev_range.get("max", 0)
    if revenue:
        in_appetite = min_rev <= revenue <= max_rev
        revenue_factors = rf.get("revenue_factors", {})
        matched_rev_factor = None
        for tier_name, factor in revenue_factors.items():
            if _revenue_matches_tier(revenue, tier_name):
                matched_rev_factor = (tier_name, factor)
                break
        rev_context = f"Revenue ${revenue:,.0f} is {'WITHIN' if in_appetite else 'OUTSIDE'} appetite range (${min_rev:,}-${max_rev:,})."
        if matched_rev_factor:
            rev_context += f" Revenue tier: {matched_rev_factor[0]}, factor: {matched_rev_factor[1]}."
        results.append({"title": "Revenue Assessment", "content": rev_context})

    # Security posture context
    sec_req = appetite.get("security_requirements", {})
    min_score = sec_req.get("minimum_score", 0)
    required_controls = sec_req.get("required_controls", [])
    if security_score:
        meets_minimum = security_score >= min_score
        security_factors = rf.get("security_factors", {})
        matched_sec_factor = None
        for tier_name, factor in security_factors.items():
            if _score_matches_tier(security_score, tier_name):
                matched_sec_factor = (tier_name, factor)
                break
        sec_context = (
            f"Security maturity score: {security_score}/10. "
            f"{'MEETS' if meets_minimum else 'BELOW'} minimum requirement of {min_score}. "
            f"Required controls: {required_controls}."
        )
        if matched_sec_factor:
            sec_context += f" Security tier: {matched_sec_factor[0]}, factor: {matched_sec_factor[1]}."

        # Check which required controls the submission has
        has_mfa = merged.get("has_mfa", False)
        has_endpoint = merged.get("has_endpoint_protection", False)
        missing_controls = []
        if "MFA" in required_controls and not has_mfa:
            missing_controls.append("MFA")
        if "endpoint_protection" in required_controls and not has_endpoint:
            missing_controls.append("endpoint_protection")
        if missing_controls:
            sec_context += f" MISSING REQUIRED CONTROLS: {missing_controls}. May require referral."

        results.append({"title": "Security Posture Assessment", "content": sec_context})

    # Prior incidents context
    max_incidents = appetite.get("max_prior_incidents", 3)
    if prior_incidents is not None:
        incident_factors = rf.get("incident_factors", {})
        matched_inc_factor = None
        for tier_name, factor in incident_factors.items():
            if _incidents_match_tier(prior_incidents, tier_name):
                matched_inc_factor = (tier_name, factor)
                break
        inc_context = (
            f"Prior incidents: {prior_incidents}. "
            f"Maximum allowed: {max_incidents}. "
            f"{'WITHIN LIMITS.' if prior_incidents <= max_incidents else 'EXCEEDS MAXIMUM — decline or refer.'}"
        )
        if matched_inc_factor:
            inc_context += f" Incident tier: {matched_inc_factor[0]}, factor: {matched_inc_factor[1]}."
        results.append({"title": "Incident History Assessment", "content": inc_context})

    logger.info(
        "prompts.submission_specific_guidelines",
        lob=lob,
        industry=industry,
        sic_code=sic_code,
        guidelines_count=len(results),
    )
    return results


def _revenue_matches_tier(revenue: float, tier_name: str) -> bool:
    """Check if a revenue amount matches a named tier like 'under_1m' or '5m_15m'."""
    tier = tier_name.lower().replace("$", "").replace(",", "")
    if tier.startswith("under_") or tier.startswith("below_"):
        limit = _parse_tier_value(tier.split("_", 1)[1])
        return revenue < limit
    if tier.startswith("over_") or tier.startswith("above_"):
        limit = _parse_tier_value(tier.split("_", 1)[1])
        return revenue > limit
    parts = tier.split("_")
    if len(parts) == 2:
        low = _parse_tier_value(parts[0])
        high = _parse_tier_value(parts[1])
        if low and high:
            return low <= revenue <= high
    return False


def _score_matches_tier(score: float, tier_name: str) -> bool:
    """Check if a score matches a named tier like 'score_9_10' or 'score_3_4'."""
    tier = tier_name.lower().replace("score_", "")
    parts = tier.split("_")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]) <= score <= int(parts[1])
    return False


def _incidents_match_tier(count: int, tier_name: str) -> bool:
    """Check if an incident count matches a named tier like '0_incidents' or '3_incidents'."""
    tier = tier_name.lower().replace("_incidents", "").replace("_incident", "")
    if tier.endswith("+"):
        return count >= int(tier[:-1])
    if tier.isdigit():
        return count == int(tier)
    parts = tier.split("_")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]) <= count <= int(parts[1])
    return False


def _parse_tier_value(s: str) -> float:
    """Parse tier boundary like '1m', '15m', '500k' into a number."""
    s = s.strip().lower()
    if s.endswith("m"):
        try:
            return float(s[:-1]) * 1_000_000
        except ValueError:
            return 0
    if s.endswith("k"):
        try:
            return float(s[:-1]) * 1_000
        except ValueError:
            return 0
    try:
        return float(s)
    except ValueError:
        return 0


def _get_knowledge_context_for_lob(lob: str = "cyber") -> str:
    """Build a comprehensive knowledge context string for a LOB."""
    mem = _knowledge_store()
    gl = mem.get_guidelines(lob)
    if not gl:
        return ""

    parts: list[str] = []

    appetite = gl.get("appetite", {})
    if appetite:
        parts.append(
            f"APPETITE: Target industries: {appetite.get('target_industries', [])}. "
            f"SIC codes preferred: {appetite.get('sic_codes', {}).get('preferred', [])}. "
            f"Revenue range: ${appetite.get('revenue_range', {}).get('min', 0):,} - "
            f"${appetite.get('revenue_range', {}).get('max', 0):,}. "
            f"Security min score: {appetite.get('security_requirements', {}).get('minimum_score', 'N/A')}. "
            f"Required controls: {appetite.get('security_requirements', {}).get('required_controls', [])}. "
            f"Max prior incidents: {appetite.get('max_prior_incidents', 'N/A')}."
        )

    rf = gl.get("rating_factors", {})
    if rf:
        parts.append(
            f"RATING: Base rate ${rf.get('base_rate_per_1000', 0)}/1000 revenue. "
            f"Industry factors: {json.dumps(rf.get('industry_factors', {}), default=str)}. "
            f"Security factors: {json.dumps(rf.get('security_factors', {}), default=str)}. "
            f"Revenue factors: {json.dumps(rf.get('revenue_factors', {}), default=str)}. "
            f"Incident factors: {json.dumps(rf.get('incident_factors', {}), default=str)}. "
            f"Min premium: ${rf.get('minimum_premium', 0):,}."
        )

    cov = gl.get("coverage_options", [])
    if cov:
        cov_strs = [f"{c['name']} (limit ${c['default_limit']:,}): {c['description']}" for c in cov]
        parts.append("COVERAGES: " + " | ".join(cov_strs))

    excl = gl.get("exclusions", [])
    if excl:
        parts.append(f"EXCLUSIONS: {', '.join(excl)}")

    subj = gl.get("subjectivities", [])
    if subj:
        parts.append(f"SUBJECTIVITIES: {', '.join(subj)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_triage_prompt(
    submission: dict[str, Any],
    guidelines: list[dict[str, Any]] | None = None,
) -> str:
    """Build a structured prompt for the submission triage agent."""
    lob = submission.get("line_of_business", "cyber")
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
    lob = submission.get("line_of_business", "cyber")
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
        kb_ctx = _get_knowledge_context_for_lob(lob)
        if kb_ctx:
            prompt += f"PRICING GUIDELINES (from knowledge base):\n{kb_ctx}\n\n"
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


# ---------------------------------------------------------------------------
# Billing prompt builder (#77)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Document prompt builder (#78)
# ---------------------------------------------------------------------------


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
