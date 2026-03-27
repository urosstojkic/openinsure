"""structlog processor that redacts PII from log output.

Installed during application startup so every structured-log event
automatically has sensitive values replaced with ``***``.
"""

from __future__ import annotations

import re
from typing import Any

# Fields whose values should always be fully redacted
_PII_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "email",
        "contact_email",
        "applicant_name",
        "policyholder_name",
        "insured_name",
        "reported_by",
        "contact_phone",
        "phone",
        "ssn",
        "social_security_number",
        "tax_id",
        "tax_number",
        "tin",
        "date_of_birth",
        "dob",
        "bank_account",
        "routing_number",
        "credit_card",
        "card_number",
    }
)

# Patterns matched against string values regardless of field name
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

_REDACTED = "***"


def _redact_value(value: Any) -> Any:
    """Replace PII patterns inside a string value."""
    if not isinstance(value, str):
        return value
    result = _SSN_RE.sub(_REDACTED, value)
    return _EMAIL_RE.sub(_REDACTED, result)


def _redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact PII fields in a dict."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in _PII_FIELD_NAMES:
            result[key] = _REDACTED
        elif isinstance(value, dict):
            result[key] = _redact_dict(value)
        elif isinstance(value, list):
            result[key] = [_redact_dict(v) if isinstance(v, dict) else _redact_value(v) for v in value]
        else:
            result[key] = _redact_value(value)
    return result


def redact_pii_processor(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """structlog processor — masks PII fields and patterns in every log event."""
    return _redact_dict(event_dict)
