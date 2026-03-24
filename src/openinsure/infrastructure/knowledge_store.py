"""In-memory knowledge store — the institutional knowledge backbone of OpenInsure.

Provides rich, structured insurance data that works as the default knowledge
source for all Foundry agents.  Cosmos DB is an *optional* enhancement; this
module guarantees every agent has comprehensive context even without Azure.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ======================================================================
# Underwriting Guidelines
# ======================================================================

UNDERWRITING_GUIDELINES: dict[str, dict[str, Any]] = {
    "cyber": {
        "appetite": {
            "target_industries": [
                "Technology",
                "Financial Services",
                "Professional Services",
                "Healthcare",
            ],
            "sic_codes": {
                "preferred": ["7371-7379", "6020-6099"],
                "acceptable": ["8011-8099", "4811-4899"],
                "declined": ["1000-1499", "2000-2099"],
            },
            "revenue_range": {"min": 500_000, "max": 50_000_000},
            "employee_range": {"min": 10, "max": 5000},
            "security_requirements": {
                "minimum_score": 4,
                "required_controls": ["MFA", "endpoint_protection"],
                "preferred_controls": [
                    "backup_strategy",
                    "incident_response_plan",
                    "security_training",
                ],
            },
            "max_prior_incidents": 3,
        },
        "rating_factors": {
            "base_rate_per_1000": 1.50,
            "industry_factors": {
                "technology": 0.85,
                "financial_services": 1.20,
                "healthcare": 1.40,
                "retail": 1.15,
                "manufacturing": 1.30,
                "professional_services": 0.95,
                "education": 1.10,
            },
            "security_factors": {
                "score_9_10": 0.70,
                "score_7_8": 0.85,
                "score_5_6": 1.00,
                "score_3_4": 1.25,
                "score_1_2": 1.60,
            },
            "revenue_factors": {
                "under_1m": 0.80,
                "1m_5m": 0.90,
                "5m_15m": 1.00,
                "15m_30m": 1.10,
                "30m_50m": 1.25,
            },
            "incident_factors": {
                "0_incidents": 0.90,
                "1_incident": 1.00,
                "2_incidents": 1.15,
                "3_incidents": 1.35,
            },
            "minimum_premium": 2500,
        },
        "coverage_options": [
            {
                "name": "First-Party Data Breach Response",
                "default_limit": 1_000_000,
                "description": (
                    "Covers forensic investigation, notification costs, credit monitoring, and crisis management"
                ),
            },
            {
                "name": "Business Interruption",
                "default_limit": 500_000,
                "description": "Covers lost income and extra expenses from network downtime",
            },
            {
                "name": "Cyber Extortion / Ransomware",
                "default_limit": 500_000,
                "description": "Covers ransom payments and negotiation costs",
            },
            {
                "name": "Third-Party Liability",
                "default_limit": 1_000_000,
                "description": ("Covers regulatory fines, legal defense, and settlements"),
            },
            {
                "name": "Media Liability",
                "default_limit": 250_000,
                "description": ("Covers IP infringement, defamation claims from digital content"),
            },
        ],
        "exclusions": [
            "Acts of war",
            "Known prior breaches",
            "Unpatched critical vulnerabilities (>90 days)",
            "Deliberate non-compliance",
            "Infrastructure failure (power/telecom)",
        ],
        "subjectivities": [
            "Completed cyber risk application",
            "Security assessment questionnaire",
            "Prior 3-year loss history",
            "Network diagram (if >100 employees)",
        ],
    },
    "general_liability": {
        "appetite": {
            "target_industries": [
                "Professional Services",
                "Retail",
                "Manufacturing",
                "Construction",
            ],
            "sic_codes": {
                "preferred": ["7300-7399", "5200-5999"],
                "acceptable": ["1500-1799", "2000-3999"],
                "declined": ["1300-1399", "4900-4999"],
            },
            "revenue_range": {"min": 500_000, "max": 2_000_000_000},
            "employee_range": {"min": 5, "max": 10_000},
            "security_requirements": {
                "minimum_score": 0,
                "required_controls": [],
                "preferred_controls": ["safety_program", "quality_control"],
            },
            "max_prior_incidents": 5,
        },
        "rating_factors": {
            "base_rate_per_1000": 2.00,
            "industry_factors": {
                "professional_services": 0.80,
                "retail": 1.00,
                "manufacturing": 1.20,
                "construction": 1.50,
                "hospitality": 1.10,
            },
            "revenue_factors": {
                "under_1m": 0.85,
                "1m_10m": 0.95,
                "10m_100m": 1.00,
                "100m_500m": 1.10,
                "over_500m": 1.25,
            },
            "incident_factors": {
                "0_incidents": 0.85,
                "1_2_incidents": 1.00,
                "3_5_incidents": 1.30,
            },
            "minimum_premium": 2500,
        },
        "coverage_options": [
            {
                "name": "Bodily Injury & Property Damage",
                "default_limit": 1_000_000,
                "description": "Covers third-party bodily injury and property damage claims",
            },
            {
                "name": "Personal & Advertising Injury",
                "default_limit": 1_000_000,
                "description": "Covers libel, slander, copyright infringement in advertising",
            },
            {
                "name": "Products-Completed Operations",
                "default_limit": 2_000_000,
                "description": "Aggregate limit for products and completed operations claims",
            },
        ],
        "exclusions": [
            "Expected or intended injury",
            "Contractual liability (unless insured contract)",
            "Workers compensation obligations",
            "Professional errors & omissions",
            "Pollution (unless sudden & accidental)",
        ],
        "subjectivities": [
            "Completed GL application",
            "5-year loss runs",
            "Certificate of occupancy (if applicable)",
        ],
    },
    "property": {
        "appetite": {
            "target_industries": [
                "Commercial Real Estate",
                "Manufacturing",
                "Retail",
                "Warehousing",
            ],
            "sic_codes": {
                "preferred": ["6500-6599", "5200-5999"],
                "acceptable": ["2000-3999", "4200-4299"],
                "declined": ["1300-1399"],
            },
            "revenue_range": {"min": 100_000, "max": 500_000_000},
            "employee_range": {"min": 1, "max": 20_000},
            "security_requirements": {
                "minimum_score": 0,
                "required_controls": ["sprinkler_system"],
                "preferred_controls": ["alarm_system", "security_guards"],
            },
            "max_prior_incidents": 4,
        },
        "rating_factors": {
            "base_rate_per_1000": 3.00,
            "construction_factors": {
                "fire_resistive": 0.70,
                "masonry_noncombustible": 0.85,
                "joisted_masonry": 1.00,
                "frame": 1.30,
            },
            "occupancy_factors": {
                "office": 0.80,
                "retail": 1.00,
                "warehouse": 1.10,
                "manufacturing": 1.30,
                "restaurant": 1.50,
            },
            "protection_factors": {
                "sprinklered": 0.70,
                "non_sprinklered": 1.00,
                "fire_alarm_only": 0.90,
            },
            "minimum_premium": 3000,
        },
        "coverage_options": [
            {
                "name": "Building Coverage",
                "default_limit": 5_000_000,
                "description": "Covers damage to the insured building structure",
            },
            {
                "name": "Business Personal Property",
                "default_limit": 1_000_000,
                "description": "Covers equipment, inventory, furniture, and fixtures",
            },
            {
                "name": "Business Income & Extra Expense",
                "default_limit": 500_000,
                "description": "Covers lost income during restoration period",
            },
        ],
        "exclusions": [
            "Flood (separate policy required)",
            "Earthquake (separate policy required)",
            "Nuclear hazard",
            "War and military action",
            "Governmental action",
            "Wear and tear / gradual deterioration",
        ],
        "subjectivities": [
            "Completed property application",
            "Building appraisal (if TIV > $5M)",
            "5-year loss history",
            "Roof inspection report (if > 15 years old)",
        ],
    },
}

# ======================================================================
# Claims Precedents
# ======================================================================

CLAIMS_PRECEDENTS: dict[str, dict[str, Any]] = {
    "ransomware": {
        "typical_reserve_range": [50_000, 750_000],
        "average_resolution_days": 45,
        "common_costs": [
            "Ransom payment (if approved)",
            "Forensic investigation",
            "Business interruption",
            "Regulatory notification",
            "Legal counsel",
        ],
        "red_flags": [
            "Multiple encryption events",
            "Exfiltration confirmed",
            "Critical infrastructure affected",
            "Regulatory data involved",
        ],
        "case_examples": [
            {
                "description": "Mid-size retailer, LockBit variant, 72hr downtime",
                "reserve": 350_000,
                "settlement": 280_000,
                "duration_days": 38,
            },
            {
                "description": "Healthcare provider, patient records encrypted",
                "reserve": 650_000,
                "settlement": 520_000,
                "duration_days": 62,
            },
        ],
    },
    "data_breach": {
        "typical_reserve_range": [25_000, 500_000],
        "average_resolution_days": 60,
        "common_costs": [
            "Notification (per record: $2-$5)",
            "Credit monitoring (per person: $10-$25/yr)",
            "Forensic investigation",
            "Regulatory fines",
            "Class action defense",
        ],
        "cost_per_record": {"low": 2, "average": 5, "high": 15},
        "notification_deadlines": {
            "GDPR": "72 hours",
            "CCPA": "72 hours",
            "HIPAA": "60 days",
            "state_avg": "30-60 days",
        },
        "case_examples": [
            {
                "description": "E-commerce platform, 50K records exposed via SQL injection",
                "reserve": 275_000,
                "settlement": 210_000,
                "duration_days": 55,
            },
            {
                "description": "SaaS provider, employee credentials compromised",
                "reserve": 120_000,
                "settlement": 95_000,
                "duration_days": 42,
            },
        ],
    },
    "business_interruption": {
        "typical_reserve_range": [30_000, 400_000],
        "average_resolution_days": 30,
        "common_costs": [
            "Lost revenue",
            "Extra expenses (temporary systems)",
            "Overtime/contractor costs",
            "Customer retention",
        ],
        "case_examples": [
            {
                "description": "Cloud provider outage affecting SaaS company, 5 days downtime",
                "reserve": 200_000,
                "settlement": 175_000,
                "duration_days": 28,
            },
        ],
    },
    "social_engineering": {
        "typical_reserve_range": [15_000, 200_000],
        "average_resolution_days": 20,
        "recovery_rate": 0.25,
        "common_patterns": [
            "CEO fraud / BEC",
            "Vendor impersonation",
            "Invoice redirect",
            "Payroll diversion",
        ],
        "common_costs": [
            "Funds lost to fraud",
            "Investigation costs",
            "Process remediation",
            "Employee training",
        ],
        "case_examples": [
            {
                "description": "BEC attack, CFO impersonation, $125K wire transfer",
                "reserve": 150_000,
                "settlement": 125_000,
                "duration_days": 18,
            },
        ],
    },
}

# ======================================================================
# Compliance Rules
# ======================================================================

COMPLIANCE_RULES: dict[str, dict[str, Any]] = {
    "eu_ai_act": {
        "articles": {
            "art_9": {
                "title": "Risk Management",
                "requirement": ("Continuous risk assessment for high-risk AI systems"),
                "implementation": "Bias monitoring with 4/5ths rule",
            },
            "art_11": {
                "title": "Technical Documentation",
                "requirement": ("Maintain comprehensive docs on AI system design, development, and monitoring"),
            },
            "art_12": {
                "title": "Record-Keeping",
                "requirement": (
                    "Automatic logging of AI system operations — every decision must produce a DecisionRecord"
                ),
            },
            "art_13": {
                "title": "Transparency",
                "requirement": ("Users informed when interacting with AI — confidence scores and reasoning visible"),
            },
            "art_14": {
                "title": "Human Oversight",
                "requirement": ("Ability for human to override AI decisions — escalation mechanism"),
            },
        },
    },
    "naic_model_bulletin": {
        "requirement": ("Insurers using AI must ensure non-discrimination, transparency, and human accountability"),
        "key_provisions": [
            "Governance framework for AI/ML systems",
            "Bias testing and monitoring",
            "Transparency in AI-driven decisions",
            "Human oversight for consequential decisions",
            "Documentation of AI system development and validation",
        ],
    },
    "gdpr": {
        "data_retention_days": 365 * 7,
        "right_to_explanation": True,
        "dpia_required_for_profiling": True,
        "key_provisions": [
            "Data processing agreement for all AI providers",
            "DPIA required for automated underwriting decisions",
            "Right to explanation for AI-driven decisions",
            "72-hour breach notification to supervisory authority",
            "Data minimization in claims processing",
        ],
        "penalties": {"max_fine_pct": 0.04, "max_fine_eur": 20_000_000},
    },
}

# ======================================================================
# Billing & Payment Rules
# ======================================================================

BILLING_RULES: dict[str, Any] = {
    "payment_terms": {
        "full_pay_discount": 0.05,
        "quarterly_surcharge": 0.02,
        "monthly_surcharge": 0.04,
    },
    "grace_periods": {
        "standard_days": 30,
        "renewal_days": 15,
        "reinstatement_window_days": 60,
    },
    "collection_escalation": {
        "reminder": {"trigger_days": 1, "max_days": 15},
        "demand_letter": {"trigger_days": 16, "max_days": 30},
        "cancellation_notice": {"trigger_days": 31, "max_days": 45},
        "cancel_for_nonpayment": {"trigger_days": 46},
    },
}

# ======================================================================
# Workflow Routing Rules
# ======================================================================

WORKFLOW_RULES: dict[str, Any] = {
    "routing": {
        "standard": {
            "description": "Normal processing path for in-appetite submissions",
            "steps": ["intake", "enrichment", "underwriting", "policy_review", "compliance"],
        },
        "expedited": {
            "description": "Fast-track for renewals and small accounts",
            "criteria": {"max_premium": 10_000, "max_risk_score": 30},
            "steps": ["intake", "underwriting", "compliance"],
        },
        "referral": {
            "description": "Manual review required — out of appetite or high risk",
            "criteria": {"min_risk_score": 70, "exceeded_authority": True},
            "steps": ["intake", "enrichment", "underwriting", "escalation"],
        },
    },
    "authority_tiers": {
        "auto_bind": {"max_premium": 25_000, "max_limit": 1_000_000},
        "senior_underwriter": {"max_premium": 100_000, "max_limit": 5_000_000},
        "committee": {"max_premium": 500_000, "max_limit": 25_000_000},
    },
}

# ======================================================================
# Analytics Benchmark Metrics
# ======================================================================

BENCHMARK_METRICS: dict[str, Any] = {
    "target_loss_ratio": 0.60,
    "target_expense_ratio": 0.30,
    "target_combined_ratio": 0.90,
    "avg_processing_time_hours": {
        "triage": 0.5,
        "underwriting": 4.0,
        "binding": 1.0,
        "claims_fnol": 2.0,
    },
    "hit_ratio_target": 0.25,
    "retention_rate_target": 0.85,
}


# ======================================================================
# InMemoryKnowledgeStore
# ======================================================================


class InMemoryKnowledgeStore:
    """Thread-safe in-memory knowledge store with full CRUD and search.

    Serves as the always-available default.  Every agent queries this
    before reasoning; Cosmos DB enriches it when available.
    """

    def __init__(self) -> None:
        self._guidelines = dict(UNDERWRITING_GUIDELINES)
        self._claims_precedents = dict(CLAIMS_PRECEDENTS)
        self._compliance_rules = dict(COMPLIANCE_RULES)
        self._billing_rules = dict(BILLING_RULES)
        self._workflow_rules = dict(WORKFLOW_RULES)
        self._benchmarks = dict(BENCHMARK_METRICS)

    # -- Guidelines --------------------------------------------------------

    def get_guidelines(self, lob: str) -> dict[str, Any] | None:
        return self._guidelines.get(lob)

    def list_guidelines(self) -> dict[str, dict[str, Any]]:
        return dict(self._guidelines)

    def update_guidelines(self, lob: str, data: dict[str, Any]) -> dict[str, Any]:
        existing = self._guidelines.get(lob, {})
        existing.update(data)
        self._guidelines[lob] = existing
        return existing

    def get_rating_factors(self, lob: str) -> dict[str, Any] | None:
        gl = self._guidelines.get(lob)
        return gl.get("rating_factors") if gl else None

    def get_coverage_options(self, lob: str) -> list[dict[str, Any]] | None:
        gl = self._guidelines.get(lob)
        return gl.get("coverage_options") if gl else None

    # -- Claims precedents -------------------------------------------------

    def get_claims_precedents(self, claim_type: str) -> dict[str, Any] | None:
        return self._claims_precedents.get(claim_type)

    def list_claims_precedents(self) -> dict[str, dict[str, Any]]:
        return dict(self._claims_precedents)

    # -- Compliance --------------------------------------------------------

    def get_compliance_rules(self, framework: str) -> dict[str, Any] | None:
        return self._compliance_rules.get(framework)

    def list_compliance_rules(self) -> dict[str, dict[str, Any]]:
        return dict(self._compliance_rules)

    # -- Billing -----------------------------------------------------------

    def get_billing_rules(self) -> dict[str, Any]:
        return dict(self._billing_rules)

    # -- Workflow ----------------------------------------------------------

    def get_workflow_rules(self) -> dict[str, Any]:
        return dict(self._workflow_rules)

    # -- Benchmarks --------------------------------------------------------

    def get_benchmarks(self) -> dict[str, Any]:
        return dict(self._benchmarks)

    # -- Search ------------------------------------------------------------

    def search(self, query: str) -> list[dict[str, Any]]:
        """Full-text substring search across all knowledge categories."""
        q = query.lower()
        results: list[dict[str, Any]] = []

        for lob, gl in self._guidelines.items():
            if q in json.dumps(gl, default=str).lower():
                results.append(
                    {
                        "id": f"guideline-{lob}",
                        "category": "guidelines",
                        "lob": lob,
                        "match_context": f"Underwriting guidelines for {lob}",
                        "data": gl,
                    }
                )

        for ctype, prec in self._claims_precedents.items():
            if q in json.dumps(prec, default=str).lower():
                results.append(
                    {
                        "id": f"precedent-{ctype}",
                        "category": "claims_precedents",
                        "claim_type": ctype,
                        "match_context": f"Claims precedents for {ctype}",
                        "data": prec,
                    }
                )

        for fw, rules in self._compliance_rules.items():
            if q in json.dumps(rules, default=str).lower():
                results.append(
                    {
                        "id": f"compliance-{fw}",
                        "category": "compliance_rules",
                        "framework": fw,
                        "match_context": f"Compliance rules for {fw}",
                        "data": rules,
                    }
                )

        if q in json.dumps(self._billing_rules, default=str).lower():
            results.append(
                {
                    "id": "billing-rules",
                    "category": "billing_rules",
                    "match_context": "Billing and payment rules",
                    "data": self._billing_rules,
                }
            )

        if q in json.dumps(self._workflow_rules, default=str).lower():
            results.append(
                {
                    "id": "workflow-rules",
                    "category": "workflow_rules",
                    "match_context": "Workflow routing rules",
                    "data": self._workflow_rules,
                }
            )

        return results


# Module-level singleton
_store: InMemoryKnowledgeStore | None = None


def get_knowledge_store() -> InMemoryKnowledgeStore:
    """Return the singleton in-memory knowledge store."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = InMemoryKnowledgeStore()
    return _store
