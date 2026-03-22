"""Seed sample data for local development.

Populates the in-memory repositories with realistic sample entities so the
dashboard has content to display immediately.  Only runs when
``settings.debug`` is ``True``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _days_ago(n: int) -> str:
    return (datetime.now(UTC) - timedelta(days=n)).isoformat()


def _days_from_now(n: int) -> str:
    return (datetime.now(UTC) + timedelta(days=n)).isoformat()


# Stable IDs so relationships work across entities
PARTY_IDS = [str(uuid.uuid4()) for _ in range(3)]
SUBMISSION_IDS = [str(uuid.uuid4()) for _ in range(5)]
POLICY_IDS = [str(uuid.uuid4()) for _ in range(3)]
CLAIM_IDS = [str(uuid.uuid4()) for _ in range(2)]
PRODUCT_ID = str(uuid.uuid4())
PRODUCT_IDS = [PRODUCT_ID] + [str(uuid.uuid4()) for _ in range(3)]
DECISION_IDS = [str(uuid.uuid4()) for _ in range(5)]
AUDIT_IDS = [str(uuid.uuid4()) for _ in range(4)]
TREATY_IDS = [str(uuid.uuid4()) for _ in range(3)]
CESSION_IDS = [str(uuid.uuid4()) for _ in range(4)]
RECOVERY_IDS = [str(uuid.uuid4()) for _ in range(2)]
RESERVE_IDS = [f"res-{i:03d}" for i in range(1, 7)]
TRIANGLE_IDS = [str(uuid.uuid4()) for _ in range(14)]
RATE_ADEQUACY_IDS = [str(uuid.uuid4()) for _ in range(7)]


def _sample_submissions() -> list[dict[str, Any]]:
    _now()
    return [
        {
            "id": SUBMISSION_IDS[0],
            "applicant_name": "Acme Cyber Corp",
            "applicant_email": "underwriting@acmecyber.com",
            "status": "received",
            "channel": "portal",
            "line_of_business": "cyber",
            "risk_data": {"annual_revenue": 5_000_000, "employee_count": 50},
            "metadata": {"broker": "MarshMcLennan"},
            "documents": [],
            "created_at": _days_ago(10),
            "updated_at": _days_ago(10),
        },
        {
            "id": SUBMISSION_IDS[1],
            "applicant_name": "TechStart Inc",
            "applicant_email": "cfo@techstart.io",
            "status": "triaging",
            "channel": "api",
            "line_of_business": "cyber",
            "risk_data": {"annual_revenue": 1_200_000, "employee_count": 15},
            "metadata": {},
            "documents": [],
            "created_at": _days_ago(7),
            "updated_at": _days_ago(6),
        },
        {
            "id": SUBMISSION_IDS[2],
            "applicant_name": "GlobalFinance Ltd",
            "applicant_email": "risk@globalfinance.com",
            "status": "quoted",
            "channel": "broker",
            "line_of_business": "cyber",
            "risk_data": {"annual_revenue": 50_000_000, "employee_count": 500},
            "metadata": {"broker": "Aon"},
            "documents": ["doc-abc123"],
            "created_at": _days_ago(14),
            "updated_at": _days_ago(3),
        },
        {
            "id": SUBMISSION_IDS[3],
            "applicant_name": "SecureHealth Systems",
            "applicant_email": "it@securehealth.org",
            "status": "bound",
            "channel": "email",
            "line_of_business": "cyber",
            "risk_data": {"annual_revenue": 8_000_000, "employee_count": 120},
            "metadata": {},
            "documents": [],
            "created_at": _days_ago(30),
            "updated_at": _days_ago(2),
        },
        {
            "id": SUBMISSION_IDS[4],
            "applicant_name": "CloudNine SaaS",
            "applicant_email": "ops@cloudnine.dev",
            "status": "underwriting",
            "channel": "portal",
            "line_of_business": "tech_eo",
            "risk_data": {"annual_revenue": 3_000_000, "employee_count": 30},
            "metadata": {},
            "documents": [],
            "created_at": _days_ago(5),
            "updated_at": _days_ago(4),
        },
    ]


def _sample_policies() -> list[dict[str, Any]]:
    return [
        {
            "id": POLICY_IDS[0],
            "submission_id": SUBMISSION_IDS[3],
            "product_id": PRODUCT_ID,
            "policy_number": "POL-ACME0001",
            "policyholder_name": "SecureHealth Systems",
            "insured_name": "SecureHealth Systems",
            "lob": "cyber",
            "status": "active",
            "effective_date": _days_ago(28),
            "expiration_date": _days_from_now(337),
            "premium": 12_500.00,
            "coverages": [{"name": "Cyber Liability", "limit": 2_000_000, "deductible": 25_000}],
            "endorsements": [],
            "metadata": {},
            "documents": [],
            "created_at": _days_ago(28),
            "updated_at": _days_ago(28),
        },
        {
            "id": POLICY_IDS[1],
            "submission_id": SUBMISSION_IDS[0],
            "product_id": PRODUCT_ID,
            "policy_number": "POL-GLOB0002",
            "policyholder_name": "Acme Cyber Corp",
            "insured_name": "Acme Cyber Corp",
            "lob": "cyber",
            "status": "pending",
            "effective_date": _days_from_now(14),
            "expiration_date": _days_from_now(379),
            "premium": 7_800.00,
            "coverages": [{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
            "endorsements": [],
            "metadata": {},
            "documents": [],
            "created_at": _days_ago(5),
            "updated_at": _days_ago(5),
        },
        {
            "id": POLICY_IDS[2],
            "submission_id": "",
            "product_id": PRODUCT_ID,
            "policy_number": "POL-EXPR0003",
            "policyholder_name": "LegacyTech Inc",
            "insured_name": "LegacyTech Inc",
            "lob": "cyber",
            "status": "expired",
            "effective_date": _days_ago(400),
            "expiration_date": _days_ago(35),
            "premium": 9_200.00,
            "coverages": [{"name": "Cyber Liability", "limit": 1_500_000, "deductible": 15_000}],
            "endorsements": [],
            "metadata": {},
            "documents": [],
            "created_at": _days_ago(400),
            "updated_at": _days_ago(35),
        },
    ]


def _sample_claims() -> list[dict[str, Any]]:
    return [
        {
            "id": CLAIM_IDS[0],
            "claim_number": "CLM-INV00001",
            "policy_id": POLICY_IDS[0],
            "policy_number": "POL-ACME0001",
            "claim_type": "data_breach",
            "status": "under_investigation",
            "description": "Unauthorized access to patient records detected via compromised VPN.",
            "date_of_loss": _days_ago(5),
            "loss_date": _days_ago(5),
            "reported_by": "CISO, SecureHealth Systems",
            "contact_email": "security@securehealth.org",
            "contact_phone": "+1-555-0199",
            "severity": "complex",
            "lob": "cyber",
            "reserves": [
                {
                    "reserve_id": str(uuid.uuid4()),
                    "category": "indemnity",
                    "amount": 150_000.0,
                    "currency": "USD",
                    "notes": "Initial reserve",
                    "created_at": _days_ago(4),
                }
            ],
            "payments": [],
            "total_reserved": 150_000.0,
            "total_paid": 0.0,
            "total_incurred": 150_000.0,
            "metadata": {"incident_severity": "high"},
            "created_at": _days_ago(5),
            "updated_at": _days_ago(4),
        },
        {
            "id": CLAIM_IDS[1],
            "claim_number": "CLM-CLS00002",
            "policy_id": POLICY_IDS[2],
            "policy_number": "POL-EXPR0003",
            "claim_type": "ransomware",
            "status": "closed",
            "description": "Ransomware attack on legacy infrastructure — resolved with backup restore.",
            "date_of_loss": _days_ago(90),
            "loss_date": _days_ago(90),
            "reported_by": "IT Director, LegacyTech Inc",
            "contact_email": "it@legacytech.com",
            "contact_phone": None,
            "severity": "moderate",
            "lob": "cyber",
            "reserves": [
                {
                    "reserve_id": str(uuid.uuid4()),
                    "category": "expense",
                    "amount": 45_000.0,
                    "currency": "USD",
                    "notes": "Forensics and restore costs",
                    "created_at": _days_ago(88),
                }
            ],
            "payments": [
                {
                    "payment_id": str(uuid.uuid4()),
                    "payee": "CyberForensics LLC",
                    "amount": 42_000.0,
                    "currency": "USD",
                    "category": "expense",
                    "reference": "INV-CF-2025-001",
                    "notes": None,
                    "created_at": _days_ago(60),
                }
            ],
            "total_reserved": 45_000.0,
            "total_paid": 42_000.0,
            "total_incurred": 42_000.0,
            "metadata": {"incident_severity": "medium"},
            "created_at": _days_ago(90),
            "updated_at": _days_ago(55),
        },
    ]


def _sample_products() -> list[dict[str, Any]]:
    return [
        {
            "id": PRODUCT_IDS[0],
            "name": "Cyber Liability",
            "product_line": "cyber",
            "description": "Comprehensive cyber liability coverage for small-to-medium businesses.",
            "version": "1.0",
            "status": "active",
            "coverages": [
                {
                    "name": "Cyber Liability",
                    "description": "Third-party liability for data breaches and cyber events.",
                    "default_limit": 1_000_000.0,
                    "max_limit": 5_000_000.0,
                    "default_deductible": 10_000.0,
                    "is_optional": False,
                },
                {
                    "name": "Business Interruption",
                    "description": "Loss of income due to cyber events.",
                    "default_limit": 500_000.0,
                    "max_limit": 2_000_000.0,
                    "default_deductible": 5_000.0,
                    "is_optional": True,
                },
            ],
            "rating_rules": {"base_rate": 1200.0},
            "underwriting_rules": {"min_revenue": 500_000, "max_revenue": 100_000_000},
            "metadata": {},
            "created_at": _days_ago(120),
            "updated_at": _days_ago(30),
        },
        {
            "id": PRODUCT_IDS[1],
            "name": "Professional Indemnity",
            "product_line": "mpl",
            "description": "Professional indemnity coverage for errors, omissions, and negligent acts.",
            "version": "1.0",
            "status": "active",
            "coverages": [
                {
                    "name": "Professional Indemnity",
                    "description": "Coverage for claims arising from professional services.",
                    "default_limit": 2_000_000.0,
                    "max_limit": 10_000_000.0,
                    "default_deductible": 25_000.0,
                    "is_optional": False,
                },
            ],
            "rating_rules": {"base_rate": 1800.0},
            "underwriting_rules": {"min_revenue": 250_000, "max_revenue": 200_000_000},
            "metadata": {},
            "created_at": _days_ago(120),
            "updated_at": _days_ago(30),
        },
        {
            "id": PRODUCT_IDS[2],
            "name": "Directors & Officers",
            "product_line": "mpl",
            "description": "D&O liability coverage protecting directors and officers from personal losses.",
            "version": "1.0",
            "status": "active",
            "coverages": [
                {
                    "name": "Side A — Directors & Officers",
                    "description": "Direct coverage for individual directors and officers.",
                    "default_limit": 5_000_000.0,
                    "max_limit": 25_000_000.0,
                    "default_deductible": 50_000.0,
                    "is_optional": False,
                },
                {
                    "name": "Side B — Corporate Reimbursement",
                    "description": "Reimburses the company for indemnifying directors.",
                    "default_limit": 5_000_000.0,
                    "max_limit": 25_000_000.0,
                    "default_deductible": 100_000.0,
                    "is_optional": True,
                },
            ],
            "rating_rules": {"base_rate": 2500.0},
            "underwriting_rules": {"min_revenue": 1_000_000, "max_revenue": 500_000_000},
            "metadata": {},
            "created_at": _days_ago(90),
            "updated_at": _days_ago(15),
        },
        {
            "id": PRODUCT_IDS[3],
            "name": "Technology E&O",
            "product_line": "tech_eo",
            "description": "Technology errors and omissions coverage for tech companies and service providers.",
            "version": "1.0",
            "status": "active",
            "coverages": [
                {
                    "name": "Technology E&O",
                    "description": "Coverage for technology product or service failures.",
                    "default_limit": 2_000_000.0,
                    "max_limit": 10_000_000.0,
                    "default_deductible": 15_000.0,
                    "is_optional": False,
                },
                {
                    "name": "Media Liability",
                    "description": "Coverage for IP infringement and media content errors.",
                    "default_limit": 1_000_000.0,
                    "max_limit": 5_000_000.0,
                    "default_deductible": 10_000.0,
                    "is_optional": True,
                },
            ],
            "rating_rules": {"base_rate": 1500.0},
            "underwriting_rules": {"min_revenue": 500_000, "max_revenue": 150_000_000},
            "metadata": {},
            "created_at": _days_ago(90),
            "updated_at": _days_ago(15),
        },
    ]


def _sample_decisions() -> list[dict[str, Any]]:
    return [
        {
            "id": DECISION_IDS[0],
            "decision_type": "triage",
            "entity_id": SUBMISSION_IDS[0],
            "entity_type": "submission",
            "model_id": "triage-agent-v1",
            "model_version": "0.1.0",
            "input_summary": {"applicant": "Acme Cyber Corp", "industry": "technology"},
            "output_summary": {"risk_score": 0.35, "recommendation": "proceed_to_quote"},
            "confidence": 0.92,
            "explanation": "Low risk profile based on industry benchmarks and security posture.",
            "human_override": False,
            "override_reason": None,
            "created_at": _days_ago(9),
        },
        {
            "id": DECISION_IDS[1],
            "decision_type": "underwriting",
            "entity_id": SUBMISSION_IDS[2],
            "entity_type": "submission",
            "model_id": "underwriting-agent-v1",
            "model_version": "0.1.0",
            "input_summary": {"applicant": "GlobalFinance Ltd", "revenue": 50_000_000},
            "output_summary": {"risk_score": 0.58, "recommendation": "refer_to_senior"},
            "confidence": 0.78,
            "explanation": "Higher revenue band triggers senior underwriter review.",
            "human_override": True,
            "override_reason": "Senior UW approved after additional documentation review.",
            "created_at": _days_ago(5),
        },
        {
            "id": DECISION_IDS[2],
            "decision_type": "claims",
            "entity_id": CLAIM_IDS[0],
            "entity_type": "claim",
            "model_id": "claims-triage-v1",
            "model_version": "0.1.0",
            "input_summary": {"claim_type": "data_breach", "severity": "high"},
            "output_summary": {"recommended_reserve": 150_000, "priority": "urgent"},
            "confidence": 0.85,
            "explanation": "High-severity data breach with potential regulatory exposure.",
            "human_override": False,
            "override_reason": None,
            "created_at": _days_ago(4),
        },
        {
            "id": DECISION_IDS[3],
            "decision_type": "pricing",
            "entity_id": SUBMISSION_IDS[3],
            "entity_type": "submission",
            "model_id": "rating-engine-v1",
            "model_version": "1.0.0",
            "input_summary": {"revenue": 8_000_000, "employees": 120},
            "output_summary": {"premium": 12_500, "currency": "USD"},
            "confidence": 0.95,
            "explanation": "Standard rating for mid-market healthcare vertical.",
            "human_override": False,
            "override_reason": None,
            "created_at": _days_ago(30),
        },
        {
            "id": DECISION_IDS[4],
            "decision_type": "fraud_detection",
            "entity_id": CLAIM_IDS[1],
            "entity_type": "claim",
            "model_id": "fraud-detection-v1",
            "model_version": "0.2.0",
            "input_summary": {"claim_type": "ransomware", "amount": 45_000},
            "output_summary": {"fraud_score": 0.12, "flag": False},
            "confidence": 0.91,
            "explanation": "Low fraud indicators — claim consistent with incident pattern.",
            "human_override": False,
            "override_reason": None,
            "created_at": _days_ago(88),
        },
    ]


def _sample_audit_events() -> list[dict[str, Any]]:
    return [
        {
            "id": AUDIT_IDS[0],
            "timestamp": _days_ago(10),
            "actor": "portal",
            "action": "submission.created",
            "entity_type": "submission",
            "entity_id": SUBMISSION_IDS[0],
            "details": {"applicant": "Acme Cyber Corp"},
        },
        {
            "id": AUDIT_IDS[1],
            "timestamp": _days_ago(9),
            "actor": "triage-agent-v1",
            "action": "decision.recorded",
            "entity_type": "submission",
            "entity_id": SUBMISSION_IDS[0],
            "details": {"decision_id": DECISION_IDS[0]},
        },
        {
            "id": AUDIT_IDS[2],
            "timestamp": _days_ago(5),
            "actor": "underwriting-agent-v1",
            "action": "decision.recorded",
            "entity_type": "submission",
            "entity_id": SUBMISSION_IDS[2],
            "details": {"decision_id": DECISION_IDS[1]},
        },
        {
            "id": AUDIT_IDS[3],
            "timestamp": _days_ago(4),
            "actor": "claims-triage-v1",
            "action": "decision.recorded",
            "entity_type": "claim",
            "entity_id": CLAIM_IDS[0],
            "details": {"decision_id": DECISION_IDS[2]},
        },
    ]


def _sample_treaties() -> list[dict[str, Any]]:
    return [
        {
            "id": TREATY_IDS[0],
            "treaty_number": "TRE-QS2025001",
            "treaty_type": "quota_share",
            "reinsurer_name": "Swiss Re",
            "status": "active",
            "effective_date": _days_ago(180),
            "expiration_date": _days_from_now(185),
            "lines_of_business": ["cyber", "tech_eo"],
            "retention": 0.70,
            "limit": 5_000_000,
            "rate": 0.30,
            "capacity_total": 15_000_000,
            "capacity_used": 3_750_000,
            "reinstatements": 1,
            "description": "30% quota share on cyber and tech E&O portfolio.",
            "created_at": _days_ago(180),
            "updated_at": _days_ago(5),
        },
        {
            "id": TREATY_IDS[1],
            "treaty_number": "TRE-XL2025001",
            "treaty_type": "excess_of_loss",
            "reinsurer_name": "Munich Re",
            "status": "active",
            "effective_date": _days_ago(180),
            "expiration_date": _days_from_now(185),
            "lines_of_business": ["cyber"],
            "retention": 500_000,
            "limit": 4_500_000,
            "rate": 0.12,
            "capacity_total": 10_000_000,
            "capacity_used": 1_200_000,
            "reinstatements": 2,
            "description": "$4.5M xs $500K per-occurrence cyber excess-of-loss.",
            "created_at": _days_ago(180),
            "updated_at": _days_ago(10),
        },
        {
            "id": TREATY_IDS[2],
            "treaty_number": "TRE-FAC2025001",
            "treaty_type": "facultative",
            "reinsurer_name": "Lloyd's Syndicate 2525",
            "status": "active",
            "effective_date": _days_ago(28),
            "expiration_date": _days_from_now(337),
            "lines_of_business": ["cyber"],
            "retention": 0,
            "limit": 3_000_000,
            "rate": 0.18,
            "capacity_total": 3_000_000,
            "capacity_used": 600_000,
            "reinstatements": 0,
            "description": "Facultative placement for large SecureHealth account.",
            "created_at": _days_ago(28),
            "updated_at": _days_ago(28),
        },
    ]


def _sample_cessions() -> list[dict[str, Any]]:
    return [
        {
            "id": CESSION_IDS[0],
            "treaty_id": TREATY_IDS[0],
            "policy_id": POLICY_IDS[0],
            "policy_number": "POL-ACME0001",
            "ceded_premium": 3_750.00,
            "ceded_limit": 600_000,
            "cession_date": _days_ago(28),
            "created_at": _days_ago(28),
        },
        {
            "id": CESSION_IDS[1],
            "treaty_id": TREATY_IDS[0],
            "policy_id": POLICY_IDS[1],
            "policy_number": "POL-GLOB0002",
            "ceded_premium": 2_340.00,
            "ceded_limit": 300_000,
            "cession_date": _days_ago(5),
            "created_at": _days_ago(5),
        },
        {
            "id": CESSION_IDS[2],
            "treaty_id": TREATY_IDS[1],
            "policy_id": POLICY_IDS[0],
            "policy_number": "POL-ACME0001",
            "ceded_premium": 1_500.00,
            "ceded_limit": 1_500_000,
            "cession_date": _days_ago(28),
            "created_at": _days_ago(28),
        },
        {
            "id": CESSION_IDS[3],
            "treaty_id": TREATY_IDS[2],
            "policy_id": POLICY_IDS[0],
            "policy_number": "POL-ACME0001",
            "ceded_premium": 2_250.00,
            "ceded_limit": 600_000,
            "cession_date": _days_ago(28),
            "created_at": _days_ago(28),
        },
    ]


def _sample_recoveries() -> list[dict[str, Any]]:
    return [
        {
            "id": RECOVERY_IDS[0],
            "treaty_id": TREATY_IDS[1],
            "claim_id": CLAIM_IDS[1],
            "claim_number": "CLM-CLS00002",
            "recovery_amount": 12_600.00,
            "recovery_date": _days_ago(55),
            "status": "collected",
            "created_at": _days_ago(55),
        },
        {
            "id": RECOVERY_IDS[1],
            "treaty_id": TREATY_IDS[0],
            "claim_id": CLAIM_IDS[0],
            "claim_number": "CLM-INV00001",
            "recovery_amount": 45_000.00,
            "recovery_date": _days_ago(3),
            "status": "pending",
            "created_at": _days_ago(3),
        },
    ]


def _sample_actuarial_reserves() -> list[dict[str, Any]]:
    return [
        {
            "id": RESERVE_IDS[0],
            "line_of_business": "cyber",
            "accident_year": 2023,
            "reserve_type": "case",
            "carried_amount": 4_500_000,
            "indicated_amount": 4_800_000,
            "selected_amount": 4_650_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "Michael Torres",
            "notes": "Q1 2026 review — slight deterioration in large-loss corridor.",
        },
        {
            "id": RESERVE_IDS[1],
            "line_of_business": "cyber",
            "accident_year": 2023,
            "reserve_type": "ibnr",
            "carried_amount": 2_100_000,
            "indicated_amount": 2_350_000,
            "selected_amount": 2_200_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "Michael Torres",
            "notes": "Chain-ladder indication; BF cross-check within 5%.",
        },
        {
            "id": RESERVE_IDS[2],
            "line_of_business": "cyber",
            "accident_year": 2024,
            "reserve_type": "case",
            "carried_amount": 3_200_000,
            "indicated_amount": 3_400_000,
            "selected_amount": 3_300_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "",
            "notes": "Pending CFO approval.",
        },
        {
            "id": RESERVE_IDS[3],
            "line_of_business": "cyber",
            "accident_year": 2024,
            "reserve_type": "ibnr",
            "carried_amount": 1_800_000,
            "indicated_amount": 2_000_000,
            "selected_amount": 1_900_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "",
            "notes": "",
        },
        {
            "id": RESERVE_IDS[4],
            "line_of_business": "professional_liability",
            "accident_year": 2023,
            "reserve_type": "case",
            "carried_amount": 6_000_000,
            "indicated_amount": 6_200_000,
            "selected_amount": 6_100_000,
            "as_of_date": "2026-03-31",
            "analyst": "James Wright",
            "approved_by": "Michael Torres",
            "notes": "",
        },
        {
            "id": RESERVE_IDS[5],
            "line_of_business": "professional_liability",
            "accident_year": 2023,
            "reserve_type": "ibnr",
            "carried_amount": 3_500_000,
            "indicated_amount": 3_800_000,
            "selected_amount": 3_600_000,
            "as_of_date": "2026-03-31",
            "analyst": "James Wright",
            "approved_by": "Michael Torres",
            "notes": "Long-tail development — monitoring closely.",
        },
    ]


def _sample_triangle_entries() -> list[dict[str, Any]]:
    """Cyber loss development triangle — accident years 2021-2024."""
    raw = [
        (2021, 12, 1_200_000, 600_000, 600_000, 15),
        (2021, 24, 2_100_000, 1_400_000, 700_000, 18),
        (2021, 36, 2_600_000, 2_000_000, 600_000, 19),
        (2021, 48, 2_800_000, 2_500_000, 300_000, 19),
        (2021, 60, 2_850_000, 2_700_000, 150_000, 19),
        (2022, 12, 1_500_000, 700_000, 800_000, 20),
        (2022, 24, 2_500_000, 1_600_000, 900_000, 24),
        (2022, 36, 3_100_000, 2_400_000, 700_000, 25),
        (2022, 48, 3_400_000, 3_000_000, 400_000, 25),
        (2023, 12, 1_800_000, 800_000, 1_000_000, 25),
        (2023, 24, 3_000_000, 1_900_000, 1_100_000, 30),
        (2023, 36, 3_800_000, 2_800_000, 1_000_000, 32),
        (2024, 12, 2_000_000, 900_000, 1_100_000, 28),
        (2024, 24, 3_400_000, 2_100_000, 1_300_000, 34),
    ]
    return [
        {
            "id": TRIANGLE_IDS[i],
            "line_of_business": "cyber",
            "accident_year": ay,
            "development_month": dm,
            "incurred_amount": inc,
            "paid_amount": paid,
            "case_reserve": case,
            "claim_count": cnt,
        }
        for i, (ay, dm, inc, paid, case, cnt) in enumerate(raw)
    ]


def _sample_rate_adequacy() -> list[dict[str, Any]]:
    raw = [
        ("cyber", "smb-technology", "1.50", "1.72", "1.1467"),
        ("cyber", "smb-healthcare", "2.20", "2.85", "1.2955"),
        ("cyber", "smb-financial", "1.80", "1.95", "1.0833"),
        ("cyber", "mid-market-technology", "1.20", "1.35", "1.1250"),
        ("cyber", "mid-market-retail", "0.90", "0.82", "0.9111"),
        ("professional_liability", "law-firms", "3.10", "3.45", "1.1129"),
        ("professional_liability", "accounting", "2.50", "2.30", "0.9200"),
    ]
    return [
        {
            "id": RATE_ADEQUACY_IDS[i],
            "line_of_business": lob,
            "segment": seg,
            "current_rate": cr,
            "indicated_rate": ir,
            "adequacy_ratio": ar,
        }
        for i, (lob, seg, cr, ir, ar) in enumerate(raw)
    ]


async def seed_sample_data() -> None:
    """Populate the factory-provided repositories with sample data.

    Uses the same singleton repos that the API endpoints consume, so
    seeded data is immediately visible via the REST API.
    """
    from openinsure.api.billing import _repo as billing_repo
    from openinsure.api.claims import _repo as claims_repo
    from openinsure.api.compliance import _compliance_repo as compliance_repo
    from openinsure.api.policies import _repo as policies_repo
    from openinsure.api.products import _repo as products_repo
    from openinsure.api.reinsurance import _cession_repo as cession_repo
    from openinsure.api.reinsurance import _recovery_repo as recovery_repo
    from openinsure.api.reinsurance import _treaty_repo as treaty_repo
    from openinsure.api.submissions import _repo as submissions_repo
    from openinsure.infrastructure.factory import (
        get_actuarial_reserve_repository,
        get_rate_adequacy_repository,
        get_triangle_repository,
    )

    reserve_repo = get_actuarial_reserve_repository()
    triangle_repo = get_triangle_repository()
    rate_adequacy_repo = get_rate_adequacy_repository()

    # Submissions
    for sub in _sample_submissions():
        await submissions_repo.create(sub)

    # Policies
    for pol in _sample_policies():
        await policies_repo.create(pol)

    # Claims
    for clm in _sample_claims():
        await claims_repo.create(clm)

    # Products
    for prod in _sample_products():
        await products_repo.create(prod)

    # Billing — create accounts for all active policies
    await billing_repo.create(
        {
            "id": str(uuid.uuid4()),
            "policy_id": POLICY_IDS[0],
            "policyholder_name": "SecureHealth Systems",
            "status": "active",
            "total_premium": 12_500.0,
            "total_paid": 6_250.0,
            "balance_due": 6_250.0,
            "installments": 2,
            "currency": "USD",
            "billing_email": "billing@securehealth.org",
            "payments": [
                {
                    "payment_id": str(uuid.uuid4()),
                    "amount": 6_250.0,
                    "method": "ach",
                    "reference": "ACH-20250601",
                    "notes": "First installment",
                    "created_at": _days_ago(25),
                }
            ],
            "invoices": [],
            "metadata": {},
            "created_at": _days_ago(28),
            "updated_at": _days_ago(25),
        }
    )
    await billing_repo.create(
        {
            "id": str(uuid.uuid4()),
            "policy_id": POLICY_IDS[1],
            "policyholder_name": "Acme Cyber Corp",
            "status": "active",
            "total_premium": 7_800.0,
            "total_paid": 0.0,
            "balance_due": 7_800.0,
            "installments": 4,
            "currency": "USD",
            "billing_email": "accounting@acmecyber.com",
            "payments": [],
            "invoices": [
                {
                    "invoice_id": str(uuid.uuid4()),
                    "account_id": "",
                    "amount": 1_950.0,
                    "status": "issued",
                    "due_date": _days_from_now(14),
                    "description": "Q1 premium installment",
                    "line_items": [],
                    "created_at": _days_ago(5),
                }
            ],
            "metadata": {},
            "created_at": _days_ago(5),
            "updated_at": _days_ago(5),
        }
    )
    await billing_repo.create(
        {
            "id": str(uuid.uuid4()),
            "policy_id": POLICY_IDS[2],
            "policyholder_name": "LegacyTech Inc",
            "status": "paid_in_full",
            "total_premium": 9_200.0,
            "total_paid": 9_200.0,
            "balance_due": 0.0,
            "installments": 1,
            "currency": "USD",
            "billing_email": "finance@legacytech.com",
            "payments": [
                {
                    "payment_id": str(uuid.uuid4()),
                    "amount": 9_200.0,
                    "method": "wire",
                    "reference": "WIRE-20240915",
                    "notes": "Full premium payment",
                    "created_at": _days_ago(400),
                }
            ],
            "invoices": [],
            "metadata": {},
            "created_at": _days_ago(400),
            "updated_at": _days_ago(400),
        }
    )

    # Compliance — only seed audit events; decisions are recorded only when
    # real Foundry agents run (no synthetic/mock decision data).
    await compliance_repo.clear_audit_events()
    for evt in _sample_audit_events():
        await compliance_repo.add_audit_event(evt)

    # Reinsurance — treaties, cessions, recoveries
    for treaty in _sample_treaties():
        await treaty_repo.create(treaty)

    for cession in _sample_cessions():
        await cession_repo.create(cession)

    for recovery in _sample_recoveries():
        await recovery_repo.create(recovery)

    # Actuarial — reserves, triangles, rate adequacy
    for reserve in _sample_actuarial_reserves():
        await reserve_repo.create(reserve)

    for entry in _sample_triangle_entries():
        await triangle_repo.create(entry)

    for ra in _sample_rate_adequacy():
        await rate_adequacy_repo.create(ra)
