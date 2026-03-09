"""Tests for the Submission domain entity."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from openinsure.domain.submission import (
    CyberRiskData,
    Document,
    Submission,
    SubmissionChannel,
    SubmissionStatus,
    TriageResult,
)


def _make_submission(**overrides) -> Submission:
    """Helper to create a submission with sensible defaults."""
    defaults = {
        "submission_number": "SUB-001",
        "channel": SubmissionChannel.email,
        "line_of_business": "cyber",
        "applicant": uuid4(),
        "requested_effective_date": date(2026, 7, 1),
        "requested_expiration_date": date(2027, 7, 1),
    }
    defaults.update(overrides)
    return Submission(**defaults)


class TestCreateSubmission:
    """Test creating a submission."""

    def test_create_submission(self):
        sub = _make_submission()
        assert sub.submission_number == "SUB-001"
        assert sub.status == SubmissionStatus.received
        assert sub.channel == SubmissionChannel.email
        assert sub.line_of_business == "cyber"
        assert sub.id is not None

    def test_create_submission_via_api(self):
        sub = _make_submission(channel=SubmissionChannel.api)
        assert sub.channel == SubmissionChannel.api

    def test_create_submission_via_portal(self):
        sub = _make_submission(channel=SubmissionChannel.portal)
        assert sub.channel == SubmissionChannel.portal


class TestSubmissionStatusTransitions:
    """Test submission status transitions."""

    def test_default_status_is_received(self):
        sub = _make_submission()
        assert sub.status == SubmissionStatus.received

    def test_transition_to_triaging(self):
        sub = _make_submission()
        sub.status = SubmissionStatus.triaging
        assert sub.status == SubmissionStatus.triaging

    def test_transition_to_underwriting(self):
        sub = _make_submission()
        sub.status = SubmissionStatus.underwriting
        assert sub.status == SubmissionStatus.underwriting

    def test_transition_to_quoted(self):
        sub = _make_submission()
        sub.status = SubmissionStatus.quoted
        assert sub.status == SubmissionStatus.quoted

    def test_transition_to_bound(self):
        sub = _make_submission()
        sub.status = SubmissionStatus.bound
        assert sub.status == SubmissionStatus.bound

    def test_transition_to_declined(self):
        sub = _make_submission()
        sub.status = SubmissionStatus.declined
        assert sub.status == SubmissionStatus.declined

    def test_transition_to_expired(self):
        sub = _make_submission()
        sub.status = SubmissionStatus.expired
        assert sub.status == SubmissionStatus.expired


class TestCyberRiskDataValidation:
    """Test CyberRiskData validation."""

    def test_valid_cyber_risk_data(self):
        data = CyberRiskData(
            annual_revenue=Decimal("5000000"),
            employee_count=50,
            industry_sic_code="7372",
            security_maturity_score=7.0,
            has_mfa=True,
            has_endpoint_protection=True,
            has_backup_strategy=True,
            has_incident_response_plan=False,
            prior_incidents=0,
        )
        assert data.annual_revenue == Decimal("5000000")
        assert data.employee_count == 50
        assert data.has_mfa is True

    def test_cyber_risk_data_with_submission(self):
        risk_data = CyberRiskData(
            annual_revenue=Decimal("10000000"),
            employee_count=200,
            industry_sic_code="6020",
            security_maturity_score=5.5,
            has_mfa=True,
            has_endpoint_protection=True,
            has_backup_strategy=False,
            has_incident_response_plan=True,
            prior_incidents=1,
        )
        sub = _make_submission(cyber_risk_data=risk_data)
        assert sub.cyber_risk_data is not None
        assert sub.cyber_risk_data.annual_revenue == Decimal("10000000")

    def test_invalid_employee_count_raises(self):
        with pytest.raises(Exception):
            CyberRiskData(
                annual_revenue=Decimal("1000"),
                employee_count=-1,
                industry_sic_code="7372",
                security_maturity_score=5.0,
                has_mfa=False,
                has_endpoint_protection=False,
                has_backup_strategy=False,
                has_incident_response_plan=False,
                prior_incidents=0,
            )

    def test_invalid_security_score_raises(self):
        with pytest.raises(Exception):
            CyberRiskData(
                annual_revenue=Decimal("1000"),
                employee_count=5,
                industry_sic_code="7372",
                security_maturity_score=15.0,
                has_mfa=False,
                has_endpoint_protection=False,
                has_backup_strategy=False,
                has_incident_response_plan=False,
                prior_incidents=0,
            )


class TestSubmissionWithDocuments:
    """Test submission with attached documents."""

    def test_submission_with_documents(self):
        doc = Document(
            document_type="acord_application",
            filename="acord_app.pdf",
            storage_url="https://storage.example.com/docs/acord_app.pdf",
        )
        sub = _make_submission(documents=[doc])
        assert len(sub.documents) == 1
        assert sub.documents[0].filename == "acord_app.pdf"

    def test_submission_with_multiple_documents(self):
        docs = [
            Document(
                document_type="acord_application",
                filename="acord.pdf",
                storage_url="https://storage.example.com/acord.pdf",
            ),
            Document(
                document_type="loss_run",
                filename="loss_run.pdf",
                storage_url="https://storage.example.com/loss_run.pdf",
            ),
        ]
        sub = _make_submission(documents=docs)
        assert len(sub.documents) == 2


class TestTriageResult:
    """Test triage result."""

    def test_triage_result(self):
        triage = TriageResult(
            appetite_match=True,
            risk_score=6.5,
            priority=2,
        )
        assert triage.appetite_match is True
        assert triage.risk_score == 6.5
        assert triage.priority == 2

    def test_triage_result_with_decline(self):
        triage = TriageResult(
            appetite_match=False,
            risk_score=9.0,
            priority=5,
            decline_reason="Outside risk appetite",
        )
        assert triage.appetite_match is False
        assert triage.decline_reason == "Outside risk appetite"

    def test_submission_with_triage(self):
        triage = TriageResult(
            appetite_match=True,
            risk_score=4.0,
            priority=1,
        )
        sub = _make_submission(triage_result=triage)
        assert sub.triage_result is not None
        assert sub.triage_result.appetite_match is True

    def test_triage_priority_validation(self):
        with pytest.raises(Exception):
            TriageResult(appetite_match=True, risk_score=5.0, priority=0)

        with pytest.raises(Exception):
            TriageResult(appetite_match=True, risk_score=5.0, priority=6)


class TestSubmissionSerialization:
    """Test submission serialization."""

    def test_submission_serialization(self):
        sub = _make_submission(
            quoted_premium=Decimal("15000.00"),
        )
        data = sub.model_dump()
        assert data["submission_number"] == "SUB-001"
        assert data["status"] == "received"
        assert data["channel"] == "email"

    def test_submission_roundtrip(self):
        sub = _make_submission()
        data = sub.model_dump()
        restored = Submission(**data)
        assert restored.submission_number == sub.submission_number
        assert restored.id == sub.id
        assert restored.channel == sub.channel
