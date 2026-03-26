"""Tests for the regulatory filing API endpoints and service logic.

Covers FRIA generation, transparency reports, technical documentation,
conformity assessment checklists, Schedule P exports, and bias alert
threshold configuration.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with in-memory storage (no Azure dependency)."""
    from openinsure.infrastructure import factory

    # Clear factory caches so they pick up the overridden settings
    for fn in (
        factory.get_compliance_repository,
        factory.get_submission_repository,
        factory.get_policy_repository,
        factory.get_claim_repository,
        factory.get_database_adapter,
    ):
        fn.cache_clear()

    with patch.dict(os.environ, {"OPENINSURE_STORAGE_MODE": "memory", "OPENINSURE_SQL_CONNECTION_STRING": ""}):
        from openinsure.main import create_app

        app = create_app()
        yield TestClient(app)

    # Restore caches after test
    for fn in (
        factory.get_compliance_repository,
        factory.get_submission_repository,
        factory.get_policy_repository,
        factory.get_claim_repository,
        factory.get_database_adapter,
    ):
        fn.cache_clear()


class TestFRIAGeneration:
    """Tests for POST /api/v1/compliance/fria/generate."""

    def test_generate_fria_default(self, client: TestClient):
        resp = client.post("/api/v1/compliance/fria/generate", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_type"] == "fundamental_rights_impact_assessment"
        assert "id" in data
        assert data["id"].startswith("fria-")
        assert "generated_at" in data
        assert "sections" in data
        sections = data["sections"]
        assert "system_description" in sections
        assert "risk_assessment" in sections
        assert "mitigation_measures" in sections
        assert "monitoring_plan" in sections
        assert "human_oversight" in sections

    def test_generate_fria_with_system_id(self, client: TestClient):
        resp = client.post(
            "/api/v1/compliance/fria/generate",
            json={"system_id": "ai-sys-001"},
        )
        assert resp.status_code == 201
        data = resp.json()
        systems = data["sections"]["system_description"]["systems_assessed"]
        assert len(systems) == 1
        assert systems[0]["system_id"] == "ai-sys-001"

    def test_generate_fria_with_html(self, client: TestClient):
        resp = client.post(
            "/api/v1/compliance/fria/generate",
            json={"include_html": True},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "html" in data
        assert "<!DOCTYPE html>" in data["html"]
        assert "Fundamental Rights Impact Assessment" in data["html"]

    def test_fria_no_body(self, client: TestClient):
        resp = client.post("/api/v1/compliance/fria/generate")
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_type"] == "fundamental_rights_impact_assessment"

    def test_fria_risk_assessment_structure(self, client: TestClient):
        resp = client.post("/api/v1/compliance/fria/generate", json={})
        assert resp.status_code == 201
        risk = resp.json()["sections"]["risk_assessment"]
        areas = risk["fundamental_rights_areas"]
        assert len(areas) == 4
        rights = [a["right"] for a in areas]
        assert "Non-discrimination" in rights
        assert "Privacy and data protection" in rights
        assert "Due process" in rights
        assert "Transparency" in rights

    def test_fria_mitigation_measures(self, client: TestClient):
        resp = client.post("/api/v1/compliance/fria/generate", json={})
        assert resp.status_code == 201
        measures = resp.json()["sections"]["mitigation_measures"]["measures"]
        assert len(measures) == 4
        categories = [m["category"] for m in measures]
        assert "Bias monitoring" in categories
        assert "Human oversight" in categories
        assert all(m["status"] == "active" for m in measures)


class TestTransparencyReport:
    """Tests for POST /api/v1/compliance/transparency-report."""

    def test_generate_transparency_report(self, client: TestClient):
        resp = client.post("/api/v1/compliance/transparency-report", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_type"] == "transparency_report"
        assert data["id"].startswith("transparency-")
        assert "sections" in data
        sections = data["sections"]
        assert "ai_system_overview" in sections
        assert "decision_making_process" in sections
        assert "data_usage" in sections
        assert "confidence_and_accuracy" in sections
        assert "agent_architecture" in sections
        assert "bias_metrics" in sections

    def test_transparency_report_no_body(self, client: TestClient):
        resp = client.post("/api/v1/compliance/transparency-report")
        assert resp.status_code == 201
        assert resp.json()["document_type"] == "transparency_report"

    def test_transparency_report_agent_list(self, client: TestClient):
        resp = client.post("/api/v1/compliance/transparency-report", json={})
        agents = resp.json()["sections"]["agent_architecture"]["agents"]
        assert len(agents) == 10
        names = [a["name"] for a in agents]
        assert "Orchestrator Agent" in names
        assert "Compliance Agent" in names

    def test_transparency_report_bias_section(self, client: TestClient):
        resp = client.post("/api/v1/compliance/transparency-report", json={})
        bias = resp.json()["sections"]["bias_metrics"]
        assert "overall_status" in bias
        assert bias["method"] == "4/5ths rule (adverse impact ratio ≥ 0.8)"


class TestTechDoc:
    """Tests for POST /api/v1/compliance/tech-doc."""

    def test_generate_tech_doc(self, client: TestClient):
        resp = client.post("/api/v1/compliance/tech-doc", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_type"] == "technical_documentation_package"
        assert data["id"].startswith("techdoc-")
        sections = data["sections"]
        assert "general_description" in sections
        assert "system_architecture" in sections
        assert "data_governance" in sections
        assert "risk_management" in sections
        assert "accuracy_and_performance" in sections
        assert "monitoring_plan" in sections

    def test_tech_doc_architecture_details(self, client: TestClient):
        resp = client.post("/api/v1/compliance/tech-doc", json={})
        arch = resp.json()["sections"]["system_architecture"]
        components = arch["components"]
        assert "backend" in components
        assert "ai_platform" in components
        assert "database" in components

    def test_tech_doc_no_body(self, client: TestClient):
        resp = client.post("/api/v1/compliance/tech-doc")
        assert resp.status_code == 201


class TestConformityChecklist:
    """Tests for GET /api/v1/compliance/conformity-checklist."""

    def test_get_conformity_checklist(self, client: TestClient):
        resp = client.get("/api/v1/compliance/conformity-checklist")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "conformity_assessment_checklist"
        assert data["id"].startswith("conformity-")
        assert "summary" in data
        assert "checklist" in data
        assert len(data["checklist"]) == 9

    def test_conformity_checklist_summary(self, client: TestClient):
        resp = client.get("/api/v1/compliance/conformity-checklist")
        summary = resp.json()["summary"]
        assert "total_articles" in summary
        assert "compliant" in summary
        assert "partial" in summary
        assert "non_compliant" in summary
        assert "compliance_percentage" in summary
        assert summary["total_articles"] == 9

    def test_conformity_checklist_articles(self, client: TestClient):
        resp = client.get("/api/v1/compliance/conformity-checklist")
        checklist = resp.json()["checklist"]
        articles = [item["article"] for item in checklist]
        assert "Art. 9 — Risk Management" in articles
        assert "Art. 11 — Technical Documentation" in articles
        assert "Art. 12 — Record-Keeping" in articles
        assert "Art. 13 — Transparency" in articles
        assert "Art. 14 — Human Oversight" in articles

    def test_conformity_checklist_status_values(self, client: TestClient):
        resp = client.get("/api/v1/compliance/conformity-checklist")
        valid_statuses = {"compliant", "partial", "non_compliant"}
        for item in resp.json()["checklist"]:
            assert item["status"] in valid_statuses
            assert isinstance(item["evidence"], list)
            assert len(item["evidence"]) > 0


class TestScheduleP:
    """Tests for GET /api/v1/compliance/schedule-p."""

    def test_get_schedule_p(self, client: TestClient):
        resp = client.get("/api/v1/compliance/schedule-p")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "schedule_p"
        assert data["id"].startswith("schedule-p-")
        assert "parts" in data
        assert "total_lines_of_business" in data

    def test_schedule_p_with_lob_filter(self, client: TestClient):
        resp = client.get("/api/v1/compliance/schedule-p?lob=cyber")
        assert resp.status_code == 200
        data = resp.json()
        for part in data["parts"]:
            assert part["line_of_business"] == "cyber"

    def test_schedule_p_structure(self, client: TestClient):
        resp = client.get("/api/v1/compliance/schedule-p")
        data = resp.json()
        assert "reporting_standard" in data
        assert "NAIC" in data["reporting_standard"]
        for part in data["parts"]:
            assert "line_of_business" in part
            assert "earned_premium" in part
            assert "accident_years" in part
            assert "totals" in part


class TestBiasAlertConfig:
    """Tests for POST/GET /api/v1/compliance/bias-alerts/configure."""

    def test_get_default_config(self, client: TestClient):
        resp = client.get("/api/v1/compliance/bias-alerts/configure")
        assert resp.status_code == 200
        data = resp.json()
        assert data["four_fifths_ratio"] == 0.8
        assert data["min_sample_size"] == 10
        assert data["alert_on_single_group_flag"] is True
        assert "platform" in data["notification_channels"]

    def test_configure_bias_alerts(self, client: TestClient):
        resp = client.post(
            "/api/v1/compliance/bias-alerts/configure",
            json={
                "four_fifths_ratio": 0.75,
                "min_sample_size": 20,
                "alert_on_single_group_flag": False,
                "notification_channels": ["platform", "email"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["four_fifths_ratio"] == 0.75
        assert data["min_sample_size"] == 20
        assert data["alert_on_single_group_flag"] is False
        assert "email" in data["notification_channels"]
        assert "updated_at" in data

        # Reset to defaults
        client.post(
            "/api/v1/compliance/bias-alerts/configure",
            json={
                "four_fifths_ratio": 0.8,
                "min_sample_size": 10,
                "alert_on_single_group_flag": True,
                "notification_channels": ["platform"],
            },
        )

    def test_configure_validation(self, client: TestClient):
        resp = client.post(
            "/api/v1/compliance/bias-alerts/configure",
            json={"four_fifths_ratio": 1.5},
        )
        assert resp.status_code == 422


class TestServiceLayer:
    """Tests for the regulatory_filing service module."""

    @pytest.fixture(autouse=True)
    def _reset_factories(self):
        """Ensure in-memory storage for service-layer tests."""
        from openinsure.infrastructure import factory

        for fn in (
            factory.get_compliance_repository,
            factory.get_submission_repository,
            factory.get_policy_repository,
            factory.get_claim_repository,
            factory.get_database_adapter,
        ):
            fn.cache_clear()

        with patch.dict(os.environ, {"OPENINSURE_STORAGE_MODE": "memory", "OPENINSURE_SQL_CONNECTION_STRING": ""}):
            yield

        for fn in (
            factory.get_compliance_repository,
            factory.get_submission_repository,
            factory.get_policy_repository,
            factory.get_claim_repository,
            factory.get_database_adapter,
        ):
            fn.cache_clear()

    @pytest.mark.asyncio
    async def test_generate_fria_service(self):
        from openinsure.services.regulatory_filing import generate_fria

        result = await generate_fria()
        assert result["document_type"] == "fundamental_rights_impact_assessment"
        assert "sections" in result
        assert len(result["sections"]) == 5

    @pytest.mark.asyncio
    async def test_generate_transparency_report_service(self):
        from openinsure.services.regulatory_filing import generate_transparency_report

        result = await generate_transparency_report()
        assert result["document_type"] == "transparency_report"
        assert "sections" in result
        assert len(result["sections"]) == 6

    @pytest.mark.asyncio
    async def test_generate_tech_doc_service(self):
        from openinsure.services.regulatory_filing import generate_tech_doc

        result = await generate_tech_doc()
        assert result["document_type"] == "technical_documentation_package"

    @pytest.mark.asyncio
    async def test_generate_conformity_checklist_service(self):
        from openinsure.services.regulatory_filing import generate_conformity_checklist

        result = await generate_conformity_checklist()
        assert result["document_type"] == "conformity_assessment_checklist"
        assert len(result["checklist"]) == 9

    @pytest.mark.asyncio
    async def test_generate_schedule_p_service(self):
        from openinsure.services.regulatory_filing import generate_schedule_p

        result = await generate_schedule_p()
        assert result["document_type"] == "schedule_p"
        assert "parts" in result

    def test_bias_alert_config_defaults(self):
        from openinsure.services.regulatory_filing import (
            get_bias_alert_config,
            set_bias_alert_config,
        )

        # Ensure defaults are set
        set_bias_alert_config({"four_fifths_ratio": 0.8, "min_sample_size": 10})
        config = get_bias_alert_config()
        assert config["four_fifths_ratio"] == 0.8
        assert config["min_sample_size"] == 10

    def test_bias_alert_config_update(self):
        from openinsure.services.regulatory_filing import (
            get_bias_alert_config,
            set_bias_alert_config,
        )

        set_bias_alert_config({"four_fifths_ratio": 0.75, "min_sample_size": 15})
        config = get_bias_alert_config()
        assert config["four_fifths_ratio"] == 0.75
        assert config["min_sample_size"] == 15

        # Reset defaults for other tests
        set_bias_alert_config({"four_fifths_ratio": 0.8, "min_sample_size": 10})
