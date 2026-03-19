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
DECISION_IDS = [str(uuid.uuid4()) for _ in range(5)]
AUDIT_IDS = [str(uuid.uuid4()) for _ in range(4)]
TREATY_IDS = [str(uuid.uuid4()) for _ in range(3)]
CESSION_IDS = [str(uuid.uuid4()) for _ in range(4)]
RECOVERY_IDS = [str(uuid.uuid4()) for _ in range(2)]


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
            "claim_type": "data_breach",
            "status": "under_investigation",
            "description": "Unauthorized access to patient records detected via compromised VPN.",
            "date_of_loss": _days_ago(5),
            "reported_by": "CISO, SecureHealth Systems",
            "contact_email": "security@securehealth.org",
            "contact_phone": "+1-555-0199",
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
            "metadata": {"incident_severity": "high"},
            "created_at": _days_ago(5),
            "updated_at": _days_ago(4),
        },
        {
            "id": CLAIM_IDS[1],
            "claim_number": "CLM-CLS00002",
            "policy_id": POLICY_IDS[2],
            "claim_type": "ransomware",
            "status": "closed",
            "description": "Ransomware attack on legacy infrastructure — resolved with backup restore.",
            "date_of_loss": _days_ago(90),
            "reported_by": "IT Director, LegacyTech Inc",
            "contact_email": "it@legacytech.com",
            "contact_phone": None,
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
            "metadata": {"incident_severity": "medium"},
            "created_at": _days_ago(90),
            "updated_at": _days_ago(55),
        },
    ]


def _sample_products() -> list[dict[str, Any]]:
    return [
        {
            "id": PRODUCT_ID,
            "name": "Cyber Liability — SMB",
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
        }
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

    # Billing — create an account for the active policy
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

    # Compliance — decisions & audit events
    for dec in _sample_decisions():
        await compliance_repo.add_decision(dec)

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
