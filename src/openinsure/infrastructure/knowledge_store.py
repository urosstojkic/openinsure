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

# ======================================================================
# Industry-Specific Guidelines (Feature 3: Dynamic Knowledge Retrieval)
# ======================================================================

INDUSTRY_GUIDELINES: dict[str, dict[str, Any]] = {
    "healthcare": {
        "regulatory_frameworks": ["HIPAA", "HITECH", "state_health_privacy"],
        "key_risks": [
            "Patient data exposure (PHI)",
            "Ransomware targeting medical devices",
            "EHR system compromise",
            "Telemedicine platform vulnerabilities",
        ],
        "required_controls": [
            "HIPAA Security Rule compliance",
            "BAA with all vendors handling PHI",
            "Encrypted PHI at rest and in transit",
            "Medical device network segmentation",
        ],
        "premium_adjustment": 1.40,
        "typical_claim_types": ["data_breach", "ransomware"],
        "avg_breach_cost_per_record": 10.93,
        "regulatory_fine_exposure": "Up to $1.5M per HIPAA violation category per year",
    },
    "financial_services": {
        "regulatory_frameworks": ["GLBA", "SOX", "PCI_DSS", "NYDFS_500"],
        "key_risks": [
            "Wire fraud / funds transfer fraud",
            "Insider trading data exposure",
            "Payment card data compromise",
            "Regulatory investigation costs",
        ],
        "required_controls": [
            "PCI DSS compliance (if handling card data)",
            "SOX IT controls",
            "GLBA Safeguards Rule compliance",
            "Anti-money laundering (AML) controls",
        ],
        "premium_adjustment": 1.20,
        "typical_claim_types": ["social_engineering", "data_breach"],
        "avg_breach_cost_per_record": 5.97,
        "regulatory_fine_exposure": "NYDFS fines up to $250K per violation",
    },
    "technology": {
        "regulatory_frameworks": ["SOC2", "ISO_27001", "GDPR"],
        "key_risks": [
            "Supply chain attacks (SolarWinds-type)",
            "API vulnerabilities",
            "Cloud misconfiguration",
            "IP theft / source code exposure",
        ],
        "required_controls": [
            "SOC 2 Type II certification",
            "Secure SDLC practices",
            "Vulnerability management program",
            "Cloud security posture management",
        ],
        "premium_adjustment": 0.85,
        "typical_claim_types": ["data_breach", "business_interruption"],
        "avg_breach_cost_per_record": 4.45,
        "regulatory_fine_exposure": "GDPR up to 4% of global annual turnover",
    },
    "retail": {
        "regulatory_frameworks": ["PCI_DSS", "CCPA", "state_breach_notification"],
        "key_risks": [
            "Point-of-sale (POS) system compromise",
            "E-commerce platform breaches",
            "Customer payment card data exposure",
            "Loyalty program data theft",
        ],
        "required_controls": [
            "PCI DSS compliance",
            "Web application firewall",
            "Payment tokenization",
            "Fraud detection systems",
        ],
        "premium_adjustment": 1.15,
        "typical_claim_types": ["data_breach", "social_engineering"],
        "avg_breach_cost_per_record": 3.28,
        "regulatory_fine_exposure": "PCI fines $5K-$100K per month of non-compliance",
    },
    "manufacturing": {
        "regulatory_frameworks": ["NIST_CSF", "ICS_CERT"],
        "key_risks": [
            "OT/ICS system attacks",
            "Ransomware disrupting production",
            "Supply chain compromise",
            "Trade secret theft",
        ],
        "required_controls": [
            "OT/IT network segmentation",
            "Industrial control system monitoring",
            "Supply chain security assessment",
            "Backup and recovery for OT systems",
        ],
        "premium_adjustment": 1.30,
        "typical_claim_types": ["ransomware", "business_interruption"],
        "avg_breach_cost_per_record": 4.47,
        "regulatory_fine_exposure": "Varies by jurisdiction and industry sub-sector",
    },
    "education": {
        "regulatory_frameworks": ["FERPA", "COPPA", "state_student_privacy"],
        "key_risks": [
            "Student record exposure",
            "Research data compromise",
            "Ransomware targeting school systems",
            "Phishing targeting faculty/staff",
        ],
        "required_controls": [
            "FERPA compliance program",
            "Student data encryption",
            "Phishing awareness training",
            "Network monitoring for anomalies",
        ],
        "premium_adjustment": 1.10,
        "typical_claim_types": ["ransomware", "data_breach"],
        "avg_breach_cost_per_record": 3.65,
        "regulatory_fine_exposure": "Loss of federal funding eligibility for FERPA violations",
    },
}

# ======================================================================
# Jurisdiction-Specific Compliance Rules
# ======================================================================

JURISDICTION_RULES: dict[str, dict[str, Any]] = {
    "US": {
        "framework": "US Federal + State",
        "requirements": [
            "State breach notification laws (all 50 states)",
            "NAIC Model Bulletin on AI in insurance",
            "State-specific insurance regulations",
        ],
        "notification_deadline": "Varies by state (24 hours to 90 days)",
        "key_regulations": {
            "federal": ["GLBA", "HIPAA (if applicable)", "CCPA/CPRA (CA)"],
            "strict_states": ["CA", "NY", "MA", "IL"],
        },
    },
    "EU": {
        "framework": "EU AI Act + GDPR",
        "requirements": [
            "GDPR compliance for all personal data processing",
            "EU AI Act high-risk system classification (insurance underwriting)",
            "Right to explanation for automated decisions",
            "DPIA required for profiling-based underwriting",
            "72-hour breach notification to supervisory authority",
        ],
        "notification_deadline": "72 hours to supervisory authority",
        "key_regulations": {
            "primary": ["GDPR", "EU AI Act", "ePrivacy Directive"],
            "insurance_specific": ["Solvency II", "IDD (Insurance Distribution Directive)"],
        },
    },
    "UK": {
        "framework": "UK Data Protection Act + FCA",
        "requirements": [
            "UK GDPR compliance",
            "FCA Consumer Duty obligations",
            "ICO breach notification within 72 hours",
        ],
        "notification_deadline": "72 hours to ICO",
        "key_regulations": {
            "primary": ["UK GDPR", "Data Protection Act 2018"],
            "insurance_specific": ["FCA PRIN", "FCA SYSC"],
        },
    },
}

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
        self._industry_guidelines = dict(INDUSTRY_GUIDELINES)
        self._jurisdiction_rules = dict(JURISDICTION_RULES)

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

    # -- Industry guidelines (Feature 3) -----------------------------------

    def get_industry_guidelines(self, industry: str) -> dict[str, Any] | None:
        """Return industry-specific guidelines, risk factors, and regulatory context."""
        key = industry.lower().replace(" ", "_")
        return self._industry_guidelines.get(key)

    def list_industry_guidelines(self) -> dict[str, dict[str, Any]]:
        return dict(self._industry_guidelines)

    # -- Jurisdiction compliance (Feature 3) --------------------------------

    def get_compliance_rules_for_jurisdiction(self, territory: str) -> dict[str, Any] | None:
        """Return jurisdiction-specific compliance and regulatory rules."""
        key = territory.upper().strip()
        return self._jurisdiction_rules.get(key)

    def list_jurisdiction_rules(self) -> dict[str, dict[str, Any]]:
        return dict(self._jurisdiction_rules)

    # -- Claims precedents by risk type (Feature 3) -------------------------

    def get_claims_precedents_by_type(self, risk_type: str) -> dict[str, Any] | None:
        """Return claims precedents most relevant to a given risk type.

        Maps risk types (ransomware, phishing, etc.) to the best matching
        precedent data.
        """
        key = risk_type.lower().replace(" ", "_")
        direct = self._claims_precedents.get(key)
        if direct:
            return direct

        # Fuzzy mapping for common risk descriptions
        mappings = {
            "phishing": "social_engineering",
            "bec": "social_engineering",
            "wire_fraud": "social_engineering",
            "ransomware_attack": "ransomware",
            "encryption": "ransomware",
            "breach": "data_breach",
            "data_exposure": "data_breach",
            "pii_exposure": "data_breach",
            "downtime": "business_interruption",
            "outage": "business_interruption",
            "system_failure": "business_interruption",
        }
        mapped_key = mappings.get(key)
        if mapped_key:
            return self._claims_precedents.get(mapped_key)
        return None

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
