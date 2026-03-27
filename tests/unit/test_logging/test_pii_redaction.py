"""Tests for the PII redaction structlog processor."""

from openinsure.logging import redact_pii_processor


def _process(event_dict: dict) -> dict:
    return redact_pii_processor(None, "info", event_dict)


class TestRedactPiiProcessor:
    def test_redacts_email_field(self):
        result = _process({"event": "test", "email": "john@example.com"})
        assert result["email"] == "***"

    def test_redacts_contact_email(self):
        result = _process({"event": "test", "contact_email": "j@co.com"})
        assert result["contact_email"] == "***"

    def test_redacts_applicant_name(self):
        result = _process({"event": "test", "applicant_name": "John Doe"})
        assert result["applicant_name"] == "***"

    def test_redacts_ssn_in_value(self):
        result = _process({"event": "test", "note": "SSN is 123-45-6789"})
        assert "123-45-6789" not in result["note"]
        assert "***" in result["note"]

    def test_redacts_email_in_value(self):
        result = _process({"event": "test", "msg": "Contact user@test.org"})
        assert "user@test.org" not in result["msg"]
        assert "***" in result["msg"]

    def test_does_not_redact_safe_fields(self):
        result = _process({"event": "login", "user_id": "u-123", "status": "ok"})
        assert result["user_id"] == "u-123"
        assert result["status"] == "ok"

    def test_nested_dict_redaction(self):
        result = _process({"event": "test", "data": {"email": "x@y.com", "id": "5"}})
        assert result["data"]["email"] == "***"
        assert result["data"]["id"] == "5"

    def test_list_redaction(self):
        result = _process({"event": "test", "items": [{"ssn": "111-22-3333"}]})
        assert result["items"][0]["ssn"] == "***"

    def test_non_string_values_untouched(self):
        result = _process({"event": "test", "count": 42, "active": True})
        assert result["count"] == 42
        assert result["active"] is True
