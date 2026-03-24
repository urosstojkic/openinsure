"""Tests for dynamic knowledge retrieval (Feature 3)."""

from __future__ import annotations

from typing import Any

from openinsure.agents.prompts import (
    _estimate_primary_risk,
    _extract_industry,
    _format_dynamic_knowledge,
    _retrieve_relevant_knowledge,
)
from openinsure.infrastructure.knowledge_store import get_knowledge_store

# ---------------------------------------------------------------------------
# Sample submissions representing different industries/profiles
# ---------------------------------------------------------------------------

HEALTHCARE_SUBMISSION: dict[str, Any] = {
    "id": "sub-healthcare",
    "line_of_business": "cyber",
    "territory": "US",
    "risk_data": {
        "annual_revenue": 10_000_000,
        "employee_count": 200,
        "industry_sic_code": "8011",
        "industry": "Healthcare",
        "security_maturity_score": 6.0,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "prior_incidents": 0,
    },
}

FINTECH_SUBMISSION: dict[str, Any] = {
    "id": "sub-fintech",
    "line_of_business": "cyber",
    "territory": "EU",
    "risk_data": {
        "annual_revenue": 20_000_000,
        "employee_count": 100,
        "industry_sic_code": "6020",
        "industry": "Financial Services",
        "security_maturity_score": 8.0,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "prior_incidents": 1,
    },
}

TECH_SUBMISSION: dict[str, Any] = {
    "id": "sub-tech",
    "line_of_business": "cyber",
    "territory": "US",
    "risk_data": {
        "annual_revenue": 5_000_000,
        "employee_count": 50,
        "industry_sic_code": "7372",
        "industry": "Technology",
        "security_maturity_score": 7.0,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "prior_incidents": 0,
    },
}

LOW_SECURITY_SUBMISSION: dict[str, Any] = {
    "id": "sub-lowsec",
    "line_of_business": "cyber",
    "territory": "US",
    "risk_data": {
        "annual_revenue": 3_000_000,
        "employee_count": 30,
        "industry_sic_code": "7372",
        "industry": "Technology",
        "security_maturity_score": 2.0,
        "has_mfa": False,
        "has_endpoint_protection": False,
        "prior_incidents": 2,
    },
}


class TestExtractIndustry:
    """Test industry extraction from submission data."""

    def test_explicit_industry(self) -> None:
        assert _extract_industry(HEALTHCARE_SUBMISSION) == "healthcare"

    def test_fintech_industry(self) -> None:
        assert _extract_industry(FINTECH_SUBMISSION) == "financial_services"

    def test_tech_industry(self) -> None:
        assert _extract_industry(TECH_SUBMISSION) == "technology"

    def test_sic_code_fallback(self) -> None:
        sub: dict[str, Any] = {
            "risk_data": {"industry_sic_code": "8011"},
        }
        assert _extract_industry(sub) == "healthcare"

    def test_empty_submission(self) -> None:
        assert _extract_industry({}) == ""


class TestEstimatePrimaryRisk:
    """Test primary risk estimation."""

    def test_low_security_suggests_ransomware(self) -> None:
        assert _estimate_primary_risk(LOW_SECURITY_SUBMISSION) == "ransomware"

    def test_no_mfa_suggests_social_engineering(self) -> None:
        sub: dict[str, Any] = {
            "risk_data": {
                "security_maturity_score": 5.0,
                "has_mfa": False,
                "has_endpoint_protection": True,
                "prior_incidents": 0,
            },
        }
        assert _estimate_primary_risk(sub) == "social_engineering"

    def test_prior_incidents_suggests_breach(self) -> None:
        sub: dict[str, Any] = {
            "risk_data": {
                "security_maturity_score": 7.0,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "prior_incidents": 2,
            },
        }
        assert _estimate_primary_risk(sub) == "data_breach"


class TestRetrieveRelevantKnowledge:
    """Test dynamic knowledge retrieval."""

    async def test_healthcare_gets_industry_context(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(HEALTHCARE_SUBMISSION)
        assert knowledge["industry_specific"] is not None
        assert "HIPAA" in knowledge["industry_specific"]["regulatory_frameworks"]

    async def test_fintech_gets_pci_context(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(FINTECH_SUBMISSION)
        assert knowledge["industry_specific"] is not None
        assert "PCI_DSS" in knowledge["industry_specific"]["regulatory_frameworks"]

    async def test_eu_territory_gets_gdpr(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(FINTECH_SUBMISSION)
        assert knowledge["regulatory"] is not None
        assert "GDPR" in knowledge["regulatory"]["framework"]

    async def test_us_territory_gets_us_rules(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(HEALTHCARE_SUBMISSION)
        assert knowledge["regulatory"] is not None
        assert "US" in knowledge["regulatory"]["framework"]

    async def test_always_has_guidelines(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(TECH_SUBMISSION)
        assert knowledge["guidelines"] is not None

    async def test_always_has_rating_factors(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(TECH_SUBMISSION)
        assert knowledge["rating_factors"] is not None

    async def test_low_security_gets_ransomware_precedents(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(LOW_SECURITY_SUBMISSION)
        assert knowledge["recent_claims"] is not None
        assert "typical_reserve_range" in knowledge["recent_claims"]

    async def test_different_industries_get_different_knowledge(self) -> None:
        health_k = await _retrieve_relevant_knowledge(HEALTHCARE_SUBMISSION)
        tech_k = await _retrieve_relevant_knowledge(TECH_SUBMISSION)
        assert health_k["industry_specific"] != tech_k["industry_specific"]


class TestFormatDynamicKnowledge:
    """Test formatting of knowledge for prompt injection."""

    async def test_format_includes_industry_context(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(HEALTHCARE_SUBMISSION)
        formatted = _format_dynamic_knowledge(knowledge)
        assert "INDUSTRY-SPECIFIC CONTEXT" in formatted
        assert "HIPAA" in formatted

    async def test_format_includes_regulatory_context(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(FINTECH_SUBMISSION)
        formatted = _format_dynamic_knowledge(knowledge)
        assert "JURISDICTION-SPECIFIC REGULATORY CONTEXT" in formatted

    async def test_format_includes_claims_precedents(self) -> None:
        knowledge = await _retrieve_relevant_knowledge(LOW_SECURITY_SUBMISSION)
        formatted = _format_dynamic_knowledge(knowledge)
        assert "RELEVANT CLAIMS PRECEDENTS" in formatted

    async def test_empty_knowledge_returns_empty(self) -> None:
        formatted = _format_dynamic_knowledge({})
        assert formatted == ""


class TestKnowledgeStoreNewMethods:
    """Test the new methods added to InMemoryKnowledgeStore."""

    def test_get_industry_guidelines_healthcare(self) -> None:
        store = get_knowledge_store()
        ig = store.get_industry_guidelines("healthcare")
        assert ig is not None
        assert "HIPAA" in ig["regulatory_frameworks"]

    def test_get_industry_guidelines_technology(self) -> None:
        store = get_knowledge_store()
        ig = store.get_industry_guidelines("technology")
        assert ig is not None
        assert ig["premium_adjustment"] < 1.0

    def test_get_industry_guidelines_unknown(self) -> None:
        store = get_knowledge_store()
        ig = store.get_industry_guidelines("space_exploration")
        assert ig is None

    def test_get_compliance_rules_for_jurisdiction_us(self) -> None:
        store = get_knowledge_store()
        rules = store.get_compliance_rules_for_jurisdiction("US")
        assert rules is not None
        assert "NAIC" in rules["requirements"][1]

    def test_get_compliance_rules_for_jurisdiction_eu(self) -> None:
        store = get_knowledge_store()
        rules = store.get_compliance_rules_for_jurisdiction("EU")
        assert rules is not None
        assert "GDPR" in rules["requirements"][0]

    def test_get_claims_precedents_by_type_direct(self) -> None:
        store = get_knowledge_store()
        prec = store.get_claims_precedents_by_type("ransomware")
        assert prec is not None
        assert "typical_reserve_range" in prec

    def test_get_claims_precedents_by_type_fuzzy(self) -> None:
        store = get_knowledge_store()
        prec = store.get_claims_precedents_by_type("phishing")
        assert prec is not None  # Maps to social_engineering

    def test_get_claims_precedents_by_type_unknown(self) -> None:
        store = get_knowledge_store()
        prec = store.get_claims_precedents_by_type("alien_invasion")
        assert prec is None
