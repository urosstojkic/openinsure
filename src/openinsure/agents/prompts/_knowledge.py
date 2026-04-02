# mypy: ignore-errors
"""Knowledge retrieval helpers for prompt builders.

Provides functions to query the in-memory knowledge store, Cosmos DB,
and AI Search for underwriting guidelines, product definitions, claims
precedents, and dynamic submission-specific context.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Knowledge store access
# ---------------------------------------------------------------------------


def _knowledge_store():
    """Return the always-available in-memory knowledge store."""
    from openinsure.infrastructure.knowledge_store import get_knowledge_store

    return get_knowledge_store()


# ---------------------------------------------------------------------------
# Public knowledge retrieval helpers
# ---------------------------------------------------------------------------


async def get_product_context(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieve the product definition relevant to this submission.

    Queries AI Search for the product matching the submission's LOB/product code,
    so agents have current coverages, appetite rules, rating factors, and authority
    limits — not hardcoded defaults.

    Falls back to Cosmos DB, then SQL product repo, then in-memory knowledge store.
    """
    lob = submission.get("line_of_business", "cyber")
    product_code = submission.get("product_code", "")

    # 1. Try AI Search (fastest, always current after sync)
    try:
        from openinsure.infrastructure.factory import get_search_adapter

        search = get_search_adapter()
        if search is not None:
            query = product_code or f"{lob} insurance product"
            result = await search.search(
                query,
                filters="category eq 'product'",
                top=3,
                select=["id", "content", "category"],
            )
            hits = result.get("results", [])
            if hits:
                # Prefer exact product_code match
                for hit in hits:
                    content = hit.get("content", "")
                    if product_code and product_code.upper() in content.upper():
                        return [{"title": f"Product: {product_code}", "content": content}]
                # Otherwise return best LOB match
                for hit in hits:
                    content = hit.get("content", "")
                    if lob.lower() in content.lower():
                        return [{"title": f"Product ({lob})", "content": content}]
                # Return first result as fallback
                return [{"title": "Product Definition", "content": hits[0].get("content", "")}]
    except Exception:
        logger.debug("prompts.product_search_failed", exc_info=True)

    # 2. Try Cosmos DB products container
    try:
        from openinsure.infrastructure.factory import get_knowledge_store as get_cosmos

        store = get_cosmos()
        if store is not None:
            products = await store.query(f"product_{lob}")
            if isinstance(products, list) and products:
                return products
    except Exception:
        logger.debug("prompts.product_cosmos_failed", exc_info=True)

    # 3. Fall back to SQL product repository (bypasses knowledge pipeline)
    try:
        from openinsure.infrastructure.factory import (
            get_product_relations_repository,
            get_product_repository,
        )

        repo = get_product_repository()
        if repo is not None:
            products = await repo.list_all(skip=0, limit=100)
            # Find matching product by code or LOB
            match = None
            for p in products:
                p_code = p.get("code", p.get("product_code", ""))
                p_lob = p.get("line_of_business", p.get("product_line", ""))
                p_status = p.get("status", "")
                if product_code and p_code == product_code:
                    match = p
                    break
                if p_lob == lob and p_status == "active" and match is None:
                    match = p
            if match:
                # Load relational data for richer context
                relations = get_product_relations_repository()
                pid = str(match.get("id", ""))
                appetite_rules = match.get("appetite_rules", [])
                coverages = match.get("coverages", [])
                if relations is not None and pid:
                    rel_rules = await relations.get_appetite_rules(pid)
                    if rel_rules:
                        appetite_rules = rel_rules
                    rel_covs = await relations.get_coverages(pid)
                    if rel_covs:
                        coverages = rel_covs

                content_parts = [
                    f"PRODUCT: {match.get('name', '')} ({match.get('code', '')})",
                    f"Line of Business: {match.get('line_of_business', match.get('product_line', ''))}",
                    f"Status: {match.get('status', '')}",
                    f"Description: {match.get('description', '')}",
                ]
                if appetite_rules:
                    lines = [
                        f"  - {r.get('field', '')} {r.get('operator', '')} {r.get('value', '')}" for r in appetite_rules
                    ]
                    content_parts.append("Appetite Rules:\n" + "\n".join(lines))
                if coverages:
                    lines = [f"  - {c.get('name', '')}: limit ${c.get('default_limit', 0):,.0f}" for c in coverages]
                    content_parts.append("Coverages:\n" + "\n".join(lines))

                content = "\n".join(p for p in content_parts if p)
                return [{"title": f"Product: {match.get('code', '')}", "content": content}]
    except Exception:
        logger.debug("prompts.product_sql_failed", exc_info=True)

    # 4. No product context available — agent will use defaults
    return []


async def get_triage_context(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieve underwriting guidelines relevant to this submission.

    Returns guidelines filtered by LOB, industry, and risk profile so that
    different submissions receive different knowledge context.
    Also includes the product definition for appetite/coverage checks.
    """
    results: list[dict[str, Any]] = []

    # Product-specific knowledge (from SQL → Cosmos/Search pipeline)
    product_ctx = await get_product_context(submission)
    results.extend(product_ctx)

    # Try Cosmos DB for guidelines
    try:
        from openinsure.infrastructure.factory import get_knowledge_store as get_cosmos

        store = get_cosmos()
        if store is not None:
            lob = submission.get("line_of_business", "cyber")
            guidelines = await store.query(f"underwriting_guidelines_{lob}")
            if isinstance(guidelines, list) and guidelines:
                results.extend(guidelines)
                return results
    except Exception:
        logger.debug("prompts.knowledge_retrieval_failed", exc_info=True)

    # Fall back to rich in-memory knowledge store with submission-specific filtering
    results.extend(_submission_specific_guidelines(submission))
    return results


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


# ---------------------------------------------------------------------------
# Submission-specific filtering logic
# ---------------------------------------------------------------------------


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
        results.append(
            {
                "title": f"Industry Factor: {industry}",
                "content": (
                    f"Industry '{industry}' has a rating factor of {matched_industry_factor}. "
                    + ("This is a favorable rate (below 1.0). " if matched_industry_factor < 1.0 else "")
                    + (
                        "Elevated rate (above 1.0) — increased scrutiny required."
                        if matched_industry_factor > 1.0
                        else ""
                    )
                ),
            }
        )
    elif industry:
        results.append(
            {
                "title": f"Industry Factor: {industry}",
                "content": (
                    f"Industry '{industry}' is not in the standard rating table. "
                    "Apply default factor of 1.0 and flag for underwriter review."
                ),
            }
        )

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
                        if (
                            int(low.strip())
                            <= int(sic_code[:4] if len(sic_code) >= 4 else sic_code)
                            <= int(high.strip())
                        ):
                            sic_status = category
                            break
        results.append(
            {
                "title": f"SIC Code {sic_code} Classification",
                "content": (
                    f"SIC code {sic_code} is classified as '{sic_status}' for this LOB. "
                    f"{'WITHIN APPETITE — proceed normally.' if sic_status == 'preferred' else ''}"
                    f"{'ACCEPTABLE — standard processing.' if sic_status == 'acceptable' else ''}"
                    f"{'DECLINED CLASS — do not proceed.' if sic_status == 'declined' else ''}"
                    f"{'NOT CLASSIFIED — refer to underwriter.' if sic_status == 'unknown' else ''}"
                ),
            }
        )

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
        appetite_status = "WITHIN" if in_appetite else "OUTSIDE"
        rev_context = f"Revenue ${revenue:,.0f} is {appetite_status} appetite range (${min_rev:,}-${max_rev:,})."
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


# ---------------------------------------------------------------------------
# Tier matching helpers
# ---------------------------------------------------------------------------


def _revenue_matches_tier(revenue: float, tier_name: str) -> bool:
    """Check if a revenue amount matches a named tier like 'under_1m' or '5m_15m'."""
    tier = tier_name.lower().replace("$", "").replace(",", "")
    if tier.startswith(("under_", "below_")):
        limit = _parse_tier_value(tier.split("_", 1)[1])
        return revenue < limit
    if tier.startswith(("over_", "above_")):
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
# Feature 3: Dynamic Knowledge Retrieval (contextual RAG)
# ---------------------------------------------------------------------------


def _extract_industry(submission: dict[str, Any]) -> str:
    """Extract a normalised industry name from submission data."""
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
    industry = str(merged.get("industry", "")).lower().replace(" ", "_")

    # Map SIC code prefix to industry if no explicit industry given
    if not industry:
        sic = str(merged.get("industry_sic_code", merged.get("sic_code", "")))
        if sic:
            sic_map = {
                "73": "technology",
                "60": "financial_services",
                "61": "financial_services",
                "62": "financial_services",
                "80": "healthcare",
                "52": "retail",
                "53": "retail",
                "54": "retail",
                "20": "manufacturing",
                "30": "manufacturing",
                "82": "education",
            }
            industry = sic_map.get(sic[:2], "")
    return industry


def _estimate_primary_risk(submission: dict[str, Any]) -> str:
    """Estimate the primary risk type for this submission."""
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

    # Heuristic: check security posture and industry to estimate risk
    has_mfa = merged.get("has_mfa", False)
    has_endpoint = merged.get("has_endpoint_protection", False)
    security_score = float(merged.get("security_maturity_score", 5) or 5)
    prior_incidents = int(merged.get("prior_incidents", 0) or 0)

    if security_score < 4 and not has_endpoint:
        return "ransomware"
    if prior_incidents > 0:
        return "data_breach"
    if not has_mfa:
        return "social_engineering"
    return "data_breach"


async def _retrieve_relevant_knowledge(submission: dict[str, Any]) -> dict[str, Any]:
    """Dynamically retrieve knowledge relevant to THIS submission.

    Unlike static LOB-level retrieval, this function returns contextual
    knowledge based on the submission's industry, jurisdiction, and risk
    profile.  A healthcare submission gets HIPAA rules, a fintech gets PCI
    requirements, and a ransomware-heavy industry gets ransomware precedents.

    Returns:
        Dict with keys: guidelines, rating_factors, industry_specific,
        recent_claims, regulatory.
    """
    store = _knowledge_store()
    lob = submission.get("line_of_business", "cyber")
    industry = _extract_industry(submission)
    territory = submission.get("territory", "US")

    return {
        "guidelines": store.get_guidelines(lob),
        "rating_factors": store.get_rating_factors(lob),
        "industry_specific": store.get_industry_guidelines(industry) if industry else None,
        "recent_claims": store.get_claims_precedents_by_type(_estimate_primary_risk(submission)),
        "regulatory": store.get_compliance_rules_for_jurisdiction(territory),
    }


def _format_dynamic_knowledge(knowledge: dict[str, Any]) -> str:
    """Format dynamically retrieved knowledge into a prompt-ready string."""
    parts: list[str] = []

    industry_data = knowledge.get("industry_specific")
    if industry_data:
        parts.append("INDUSTRY-SPECIFIC CONTEXT:")
        parts.append(f"  Key risks: {', '.join(industry_data.get('key_risks', []))}")
        parts.append(f"  Required controls: {', '.join(industry_data.get('required_controls', []))}")
        parts.append(f"  Regulatory frameworks: {', '.join(industry_data.get('regulatory_frameworks', []))}")
        adj = industry_data.get("premium_adjustment")
        if adj:
            parts.append(f"  Premium adjustment factor: {adj}")
        cost = industry_data.get("avg_breach_cost_per_record")
        if cost:
            parts.append(f"  Avg breach cost per record: ${cost}")
        exposure = industry_data.get("regulatory_fine_exposure")
        if exposure:
            parts.append(f"  Regulatory fine exposure: {exposure}")

    claims_data = knowledge.get("recent_claims")
    if claims_data:
        parts.append("RELEVANT CLAIMS PRECEDENTS:")
        rr = claims_data.get("typical_reserve_range", [])
        if rr and len(rr) >= 2:
            parts.append(f"  Typical reserve range: ${rr[0]:,} - ${rr[1]:,}")
        parts.append(f"  Avg resolution: {claims_data.get('average_resolution_days', 'N/A')} days")
        red_flags = claims_data.get("red_flags", [])
        if red_flags:
            parts.append(f"  Red flags: {', '.join(red_flags)}")

    regulatory = knowledge.get("regulatory")
    if regulatory:
        parts.append("JURISDICTION-SPECIFIC REGULATORY CONTEXT:")
        parts.append(f"  Framework: {regulatory.get('framework', 'N/A')}")
        for req in regulatory.get("requirements", []):
            parts.append(f"  - {req}")
        parts.append(f"  Notification deadline: {regulatory.get('notification_deadline', 'N/A')}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Feature 1: Learning loop context helper
# ---------------------------------------------------------------------------


async def _get_learning_context(agent_name: str) -> str:
    """Get historical accuracy context for prompt injection (Feature 1)."""
    try:
        from openinsure.services.learning_loop import get_decision_tracker

        tracker = get_decision_tracker()
        return await tracker.get_prompt_context(agent_name)
    except Exception:
        logger.debug("prompts.learning_context_failed", exc_info=True)
        return ""
