"""Tests for document generation service and prompt builders (#78)."""

from __future__ import annotations

from typing import Any

import pytest

from openinsure.agents.prompts import build_billing_prompt, build_document_prompt
from openinsure.services.document_generator import DocumentGenerator

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_POLICY: dict[str, Any] = {
    "id": "pol-001",
    "policy_number": "POL-2025-ABC123",
    "policyholder_name": "Acme Cyber Corp",
    "insured_name": "Acme Cyber Corp",
    "lob": "cyber",
    "status": "active",
    "effective_date": "2025-01-01",
    "expiration_date": "2026-01-01",
    "premium": 15000.0,
    "total_premium": 15000.0,
    "coverages": [
        {
            "coverage_code": "BREACH-RESP",
            "coverage_name": "First-Party Breach Response",
            "limit": 1000000,
            "deductible": 10000,
            "premium": 4500.0,
        },
        {
            "coverage_code": "THIRD-PARTY",
            "coverage_name": "Third-Party Liability",
            "limit": 1000000,
            "deductible": 10000,
            "premium": 4500.0,
        },
        {
            "coverage_code": "REG-DEFENSE",
            "coverage_name": "Regulatory Defense & Penalties",
            "limit": 500000,
            "deductible": 10000,
            "premium": 2250.0,
        },
        {
            "coverage_code": "BUS-INTERRUPT",
            "coverage_name": "Business Interruption",
            "limit": 500000,
            "deductible": 10000,
            "premium": 2250.0,
        },
        {
            "coverage_code": "RANSOMWARE",
            "coverage_name": "Ransomware & Extortion",
            "limit": 500000,
            "deductible": 10000,
            "premium": 1500.0,
        },
    ],
    "endorsements": [],
    "metadata": {"lob": "cyber"},
}

SAMPLE_SUBMISSION: dict[str, Any] = {
    "id": "sub-001",
    "applicant_name": "Acme Cyber Corp",
    "line_of_business": "cyber",
}


# ---------------------------------------------------------------------------
# DocumentGenerator
# ---------------------------------------------------------------------------


class TestDocumentGeneratorDeclaration:
    def test_generates_declaration(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "declaration")
        assert doc["document_type"] == "declaration"
        assert "POL-2025-ABC123" in doc["title"]
        assert doc["policy_number"] == "POL-2025-ABC123"
        assert len(doc["sections"]) >= 4

    def test_declaration_contains_coverage_section(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "declaration")
        headings = [s["heading"] for s in doc["sections"]]
        assert "Coverage Summary" in headings

    def test_declaration_contains_premium(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "declaration")
        headings = [s["heading"] for s in doc["sections"]]
        assert "Premium" in headings
        premium_section = next(s for s in doc["sections"] if s["heading"] == "Premium")
        assert premium_section["data"]["total_premium"] == 15000.0

    def test_declaration_includes_endorsements_when_present(self) -> None:
        policy = {**SAMPLE_POLICY, "endorsements": [{"id": "end-1", "description": "Ransomware sublimit"}]}
        gen = DocumentGenerator()
        doc = gen.generate(policy, SAMPLE_SUBMISSION, "declaration")
        headings = [s["heading"] for s in doc["sections"]]
        assert "Endorsements" in headings


class TestDocumentGeneratorCertificate:
    def test_generates_certificate(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "certificate")
        assert doc["document_type"] == "certificate"
        assert "Certificate" in doc["title"]

    def test_certificate_sections(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "certificate")
        headings = [s["heading"] for s in doc["sections"]]
        assert "Certificate Holder" in headings
        assert "Insured" in headings
        assert "Coverages" in headings
        assert "Cancellation" in headings


class TestDocumentGeneratorSchedule:
    def test_generates_schedule(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "schedule")
        assert doc["document_type"] == "schedule"
        assert "Schedule" in doc["title"]

    def test_schedule_aggregate_limits(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "schedule")
        agg_section = next(s for s in doc["sections"] if s["heading"] == "Aggregate Limits")
        total_limit = sum(c["limit"] for c in SAMPLE_POLICY["coverages"])
        assert agg_section["data"]["total_aggregate_limit"] == total_limit

    def test_schedule_territory(self) -> None:
        gen = DocumentGenerator()
        doc = gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "schedule")
        territory_section = next(s for s in doc["sections"] if s["heading"] == "Territory & Jurisdiction")
        assert territory_section["data"]["territory"] == "Worldwide"


class TestDocumentGeneratorErrors:
    def test_unsupported_doc_type_raises(self) -> None:
        gen = DocumentGenerator()
        with pytest.raises(ValueError, match="Unsupported document type"):
            gen.generate(SAMPLE_POLICY, SAMPLE_SUBMISSION, "unknown_type")


# ---------------------------------------------------------------------------
# Prompt builders (#77 & #78)
# ---------------------------------------------------------------------------


class TestBuildBillingPrompt:
    def test_contains_system_context(self) -> None:
        prompt = build_billing_prompt(SAMPLE_POLICY, [])
        assert "Billing Agent" in prompt
        assert "SYSTEM:" in prompt

    def test_contains_policy_data(self) -> None:
        prompt = build_billing_prompt(SAMPLE_POLICY, [])
        assert "POLICY DATA" in prompt
        assert "POL-2025-ABC123" in prompt

    def test_contains_payment_history(self) -> None:
        payments = [{"amount": 5000, "method": "ach", "date": "2025-01-15"}]
        prompt = build_billing_prompt(SAMPLE_POLICY, payments)
        assert "PAYMENT HISTORY" in prompt
        assert "5000" in prompt

    def test_output_schema(self) -> None:
        prompt = build_billing_prompt(SAMPLE_POLICY, [])
        assert "default_probability" in prompt
        assert "risk_tier" in prompt
        assert "collection_priority" in prompt
        assert "recommended_action" in prompt


class TestBuildDocumentPrompt:
    def test_contains_system_context(self) -> None:
        prompt = build_document_prompt(SAMPLE_POLICY, SAMPLE_SUBMISSION, "declaration")
        assert "Document Generation Agent" in prompt
        assert "SYSTEM:" in prompt

    def test_declaration_instructions(self) -> None:
        prompt = build_document_prompt(SAMPLE_POLICY, SAMPLE_SUBMISSION, "declaration")
        assert "declarations page" in prompt.lower()
        assert "Named insured" in prompt

    def test_certificate_instructions(self) -> None:
        prompt = build_document_prompt(SAMPLE_POLICY, SAMPLE_SUBMISSION, "certificate")
        assert "Certificate of Insurance" in prompt

    def test_schedule_instructions(self) -> None:
        prompt = build_document_prompt(SAMPLE_POLICY, SAMPLE_SUBMISSION, "schedule")
        assert "Coverage Schedule" in prompt
        assert "sublimits" in prompt.lower()

    def test_output_schema(self) -> None:
        prompt = build_document_prompt(SAMPLE_POLICY, SAMPLE_SUBMISSION, "declaration")
        assert "sections" in prompt
        assert "summary" in prompt
        assert "confidence" in prompt
