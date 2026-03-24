"""Tests for structured prompt builders."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from openinsure.agents.prompts import (
    _get_rating_breakdown,
    build_claims_assessment_prompt,
    build_compliance_audit_prompt,
    build_orchestration_prompt,
    build_policy_review_prompt,
    build_prompt_for_step,
    build_triage_prompt,
    build_underwriting_prompt,
    get_triage_context,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_SUBMISSION: dict[str, Any] = {
    "id": "sub-001",
    "applicant_name": "Acme Cyber Corp",
    "line_of_business": "cyber",
    "risk_data": {
        "annual_revenue": 5_000_000,
        "employee_count": 50,
        "industry_sic_code": "7372",
        "security_maturity_score": 7.0,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "has_backup_strategy": False,
        "has_incident_response_plan": True,
        "prior_incidents": 1,
    },
}

SAMPLE_CLAIM: dict[str, Any] = {
    "id": "clm-001",
    "claim_type": "data_breach",
    "description": "Unauthorized access to customer PII",
    "severity": "moderate",
}

SAMPLE_GUIDELINES: list[dict[str, Any]] = [
    {"title": "Cyber Appetite", "content": "Accept IT/Tech with revenue $500K-$50M"},
    {"title": "Security Minimums", "content": "Require MFA and endpoint protection"},
]


# ---------------------------------------------------------------------------
# build_triage_prompt
# ---------------------------------------------------------------------------


class TestBuildTriagePrompt:
    def test_contains_system_context(self) -> None:
        prompt = build_triage_prompt(SAMPLE_SUBMISSION)
        assert "SYSTEM:" in prompt
        assert "Triage Agent" in prompt

    def test_contains_default_guidelines_when_none(self) -> None:
        prompt = build_triage_prompt(SAMPLE_SUBMISSION)
        assert "UNDERWRITING GUIDELINES" in prompt
        # Now uses rich knowledge store — check for knowledge base markers
        assert "knowledge base" in prompt or "SIC" in prompt or "Revenue" in prompt

    def test_uses_custom_guidelines(self) -> None:
        prompt = build_triage_prompt(SAMPLE_SUBMISSION, guidelines=SAMPLE_GUIDELINES)
        assert "Cyber Appetite" in prompt
        assert "Accept IT/Tech" in prompt
        # Default guidelines should NOT appear
        assert "SIC 7xxx" not in prompt

    def test_contains_submission_data(self) -> None:
        prompt = build_triage_prompt(SAMPLE_SUBMISSION)
        assert "SUBMISSION DATA" in prompt
        assert "Acme Cyber Corp" in prompt

    def test_contains_output_schema(self) -> None:
        prompt = build_triage_prompt(SAMPLE_SUBMISSION)
        assert "RESPOND WITH JSON ONLY" in prompt
        assert "appetite_match" in prompt
        assert "risk_score" in prompt
        assert "confidence" in prompt
        assert "reasoning" in prompt


# ---------------------------------------------------------------------------
# build_underwriting_prompt
# ---------------------------------------------------------------------------


class TestBuildUnderwritingPrompt:
    def test_contains_system_context(self) -> None:
        prompt = build_underwriting_prompt(SAMPLE_SUBMISSION)
        assert "Underwriting Agent" in prompt

    def test_includes_triage_result(self) -> None:
        triage = {"appetite_match": "yes", "risk_score": 5}
        prompt = build_underwriting_prompt(SAMPLE_SUBMISSION, triage_result=triage)
        assert "TRIAGE RESULT" in prompt
        assert "appetite_match" in prompt

    def test_includes_rating_breakdown(self) -> None:
        breakdown = {"final_premium": "12500.00", "factors_applied": {"industry_risk": "1.0"}}
        prompt = build_underwriting_prompt(SAMPLE_SUBMISSION, rating_breakdown=breakdown)
        assert "RATING ENGINE BREAKDOWN" in prompt
        assert "12500.00" in prompt

    def test_default_pricing_guidelines(self) -> None:
        prompt = build_underwriting_prompt(SAMPLE_SUBMISSION)
        # Now uses rich knowledge store — check for knowledge base context
        assert "PRICING GUIDELINES" in prompt or "RATING" in prompt
        assert "knowledge base" in prompt or "base_rate" in prompt or "1.5" in prompt

    def test_output_schema(self) -> None:
        prompt = build_underwriting_prompt(SAMPLE_SUBMISSION)
        assert "recommended_premium" in prompt
        assert "rating_factors" in prompt


# ---------------------------------------------------------------------------
# build_policy_review_prompt
# ---------------------------------------------------------------------------


class TestBuildPolicyReviewPrompt:
    def test_contains_review_context(self) -> None:
        prompt = build_policy_review_prompt(SAMPLE_SUBMISSION)
        assert "Policy Review Agent" in prompt
        assert "SUBMISSION DATA" in prompt

    def test_includes_underwriting_result(self) -> None:
        uw = {"risk_score": 35, "recommended_premium": 12500}
        prompt = build_policy_review_prompt(SAMPLE_SUBMISSION, underwriting_result=uw)
        assert "UNDERWRITING RESULT" in prompt
        assert "12500" in prompt

    def test_output_schema(self) -> None:
        prompt = build_policy_review_prompt(SAMPLE_SUBMISSION)
        assert "recommendation" in prompt
        assert "coverage_adequate" in prompt
        assert "terms_complete" in prompt


# ---------------------------------------------------------------------------
# build_claims_assessment_prompt
# ---------------------------------------------------------------------------


class TestBuildClaimsAssessmentPrompt:
    def test_contains_claim_data(self) -> None:
        prompt = build_claims_assessment_prompt(SAMPLE_CLAIM)
        assert "Claims Assessment Agent" in prompt
        assert "data_breach" in prompt

    def test_includes_policy(self) -> None:
        policy = {"policy_number": "POL-2025-ABC", "coverages": []}
        prompt = build_claims_assessment_prompt(SAMPLE_CLAIM, policy=policy)
        assert "POLICY DATA" in prompt
        assert "POL-2025-ABC" in prompt

    def test_includes_precedents(self) -> None:
        precedents = [{"title": "Similar breach", "summary": "Settled for $50K"}]
        prompt = build_claims_assessment_prompt(SAMPLE_CLAIM, precedents=precedents)
        assert "PRECEDENTS" in prompt
        assert "Similar breach" in prompt

    def test_output_schema(self) -> None:
        prompt = build_claims_assessment_prompt(SAMPLE_CLAIM)
        assert "severity_tier" in prompt
        assert "fraud_score" in prompt


# ---------------------------------------------------------------------------
# build_compliance_audit_prompt
# ---------------------------------------------------------------------------


class TestBuildComplianceAuditPrompt:
    def test_contains_audit_context(self) -> None:
        results = {"intake_result": {"risk_score": 5}, "underwriting_result": {"premium": 12500}}
        prompt = build_compliance_audit_prompt(results)
        assert "Compliance Audit Agent" in prompt
        assert "EU AI Act" in prompt

    def test_output_schema(self) -> None:
        prompt = build_compliance_audit_prompt({})
        assert "compliant" in prompt
        assert "transparency_score" in prompt
        assert "issues" in prompt


# ---------------------------------------------------------------------------
# build_orchestration_prompt
# ---------------------------------------------------------------------------


class TestBuildOrchestrationPrompt:
    def test_contains_entity_data(self) -> None:
        prompt = build_orchestration_prompt(SAMPLE_SUBMISSION)
        assert "Orchestration Agent" in prompt
        assert "ENTITY DATA" in prompt
        assert "Acme Cyber Corp" in prompt

    def test_output_schema(self) -> None:
        prompt = build_orchestration_prompt(SAMPLE_SUBMISSION)
        assert "processing_path" in prompt
        assert "priority" in prompt


# ---------------------------------------------------------------------------
# build_prompt_for_step (dispatcher)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBuildPromptForStep:
    async def test_orchestration_step(self) -> None:
        ctx = {"entity_data": SAMPLE_SUBMISSION}
        prompt = await build_prompt_for_step("orchestration", ctx, "sub-001", "submission")
        assert "Orchestration Agent" in prompt

    async def test_intake_step(self) -> None:
        ctx = {"entity_data": SAMPLE_SUBMISSION}
        prompt = await build_prompt_for_step("intake", ctx, "sub-001", "submission")
        assert "Triage Agent" in prompt

    async def test_underwriting_step(self) -> None:
        ctx = {"entity_data": SAMPLE_SUBMISSION, "intake_result": {"appetite_match": "yes"}}
        prompt = await build_prompt_for_step("underwriting", ctx, "sub-001", "submission")
        assert "Underwriting Agent" in prompt

    async def test_policy_review_step(self) -> None:
        ctx = {"entity_data": SAMPLE_SUBMISSION, "underwriting_result": {"premium": 12500}}
        prompt = await build_prompt_for_step("policy_review", ctx, "sub-001", "submission")
        assert "Policy Review Agent" in prompt

    async def test_assessment_claim(self) -> None:
        ctx = {"entity_data": SAMPLE_CLAIM}
        prompt = await build_prompt_for_step("assessment", ctx, "clm-001", "claim")
        assert "Claims Assessment Agent" in prompt

    async def test_assessment_renewal(self) -> None:
        ctx = {"entity_data": {"id": "pol-001", "total_premium": 12000}}
        prompt = await build_prompt_for_step("assessment", ctx, "pol-001", "policy")
        assert "Underwriting Agent" in prompt

    async def test_compliance_step(self) -> None:
        ctx = {
            "entity_data": {},
            "intake_result": {"risk_score": 5},
            "underwriting_result": {"premium": 12500},
        }
        prompt = await build_prompt_for_step("compliance", ctx, "sub-001", "submission")
        assert "Compliance Audit Agent" in prompt
        assert "intake_result" in prompt

    async def test_fallback_for_unknown_step(self) -> None:
        ctx = {"entity_data": {"id": "x"}}
        prompt = await build_prompt_for_step("unknown_step", ctx, "x", "thing")
        assert "unknown_step" in prompt
        assert "Respond with JSON" in prompt


# ---------------------------------------------------------------------------
# Knowledge retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetTriageContext:
    async def test_falls_back_to_static_guidelines(self) -> None:
        """When knowledge store is None, should return static guidelines."""
        guidelines = await get_triage_context(SAMPLE_SUBMISSION)
        assert isinstance(guidelines, list)
        # Should have at least the static cyber guidelines
        assert len(guidelines) >= 1
        assert "Cyber" in guidelines[0].get("title", "") or "cyber" in json.dumps(guidelines[0])

    @patch("openinsure.infrastructure.factory.get_knowledge_store")
    async def test_uses_knowledge_store_when_available(self, mock_store_fn: Any) -> None:
        mock_store = AsyncMock()
        mock_store.query = AsyncMock(return_value=[{"title": "Live guideline", "content": "From Cosmos"}])
        mock_store_fn.return_value = mock_store
        guidelines = await get_triage_context(SAMPLE_SUBMISSION)
        assert any(g.get("title") == "Live guideline" for g in guidelines)


# ---------------------------------------------------------------------------
# Rating breakdown helper
# ---------------------------------------------------------------------------


class TestGetRatingBreakdown:
    def test_returns_breakdown_for_valid_data(self) -> None:
        result = _get_rating_breakdown(SAMPLE_SUBMISSION)
        assert result is not None
        assert "final_premium" in result
        assert "factors_applied" in result
        assert "explanation" in result

    def test_returns_none_for_missing_revenue(self) -> None:
        result = _get_rating_breakdown({"risk_data": {}})
        assert result is None

    def test_returns_none_for_empty_submission(self) -> None:
        result = _get_rating_breakdown({})
        assert result is None
