"""Tests for risk_attribute_service — decomposition and formatting logic.

Uses pure unit tests — no database or mock needed for decompose/format.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from openinsure.services.risk_attribute_service import (
    _format_attribute,
    decompose_risk_data,
)

# ---------------------------------------------------------------------------
# decompose_risk_data
# ---------------------------------------------------------------------------


def _sample_risk_data() -> dict[str, Any]:
    return {
        "annual_revenue": 5000000,
        "employee_count": 50,
        "industry_sic_code": "7372",
        "security_maturity_score": 3.5,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "has_backup_strategy": True,
        "has_incident_response_plan": False,
        "prior_incidents": 0,
        "tech_stack": ["Python", "React", "Azure"],
    }


class TestDecomposeRiskData:
    """Test decompose_risk_data produces correct typed rows."""

    def test_decomposes_all_fields(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        assert len(rows) == 10
        names = {r["attribute_name"] for r in rows}
        assert "annual_revenue" in names
        assert "has_mfa" in names
        assert "tech_stack" in names

    def test_numeric_fields_typed_correctly(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        revenue = next(r for r in rows if r["attribute_name"] == "annual_revenue")
        assert revenue["attribute_type"] == "numeric"
        assert revenue["numeric_value"] == 5000000.0
        assert revenue["string_value"] is None

    def test_boolean_fields_typed_correctly(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        mfa = next(r for r in rows if r["attribute_name"] == "has_mfa")
        assert mfa["attribute_type"] == "boolean"
        assert mfa["boolean_value"] is True
        assert mfa["numeric_value"] is None

        irp = next(r for r in rows if r["attribute_name"] == "has_incident_response_plan")
        assert irp["boolean_value"] is False

    def test_string_fields_typed_correctly(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        sic = next(r for r in rows if r["attribute_name"] == "industry_sic_code")
        assert sic["attribute_type"] == "string"
        assert sic["string_value"] == "7372"

    def test_json_fields_typed_correctly(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        ts = next(r for r in rows if r["attribute_name"] == "tech_stack")
        assert ts["attribute_type"] == "json"
        assert json.loads(ts["string_value"]) == ["Python", "React", "Azure"]

    def test_none_values_skipped(self) -> None:
        data = {"annual_revenue": 1000000, "prior_breach_costs": None}
        rows = decompose_risk_data("sub-1", data)
        assert len(rows) == 1
        assert rows[0]["attribute_name"] == "annual_revenue"

    def test_custom_attribute_group(self) -> None:
        rows = decompose_risk_data("sub-1", {"annual_revenue": 100}, attribute_group="marine")
        assert rows[0]["attribute_group"] == "marine"

    def test_empty_data_returns_empty(self) -> None:
        rows = decompose_risk_data("sub-1", {})
        assert rows == []

    def test_display_order_assigned(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        revenue = next(r for r in rows if r["attribute_name"] == "annual_revenue")
        assert revenue["display_order"] == 1
        mfa = next(r for r in rows if r["attribute_name"] == "has_mfa")
        assert mfa["display_order"] == 5

    def test_unknown_fields_get_inferred_type(self) -> None:
        data = {"custom_score": 42, "custom_flag": True, "custom_name": "test"}
        rows = decompose_risk_data("sub-1", data)
        score = next(r for r in rows if r["attribute_name"] == "custom_score")
        assert score["attribute_type"] == "numeric"
        flag = next(r for r in rows if r["attribute_name"] == "custom_flag")
        assert flag["attribute_type"] == "boolean"
        name = next(r for r in rows if r["attribute_name"] == "custom_name")
        assert name["attribute_type"] == "string"

    def test_each_row_has_unique_id(self) -> None:
        rows = decompose_risk_data("sub-1", _sample_risk_data())
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))

    def test_submission_id_propagated(self) -> None:
        sid = str(uuid.uuid4())
        rows = decompose_risk_data(sid, {"annual_revenue": 100})
        assert rows[0]["submission_id"] == sid


# ---------------------------------------------------------------------------
# _format_attribute
# ---------------------------------------------------------------------------


class TestFormatAttribute:
    """Test _format_attribute produces correct API-friendly dicts."""

    def test_numeric_attribute(self) -> None:
        row = {
            "id": "abc",
            "submission_id": "sub-1",
            "attribute_group": "cyber_risk",
            "attribute_name": "annual_revenue",
            "attribute_type": "numeric",
            "numeric_value": 5000000.0,
            "string_value": None,
            "boolean_value": None,
            "date_value": None,
            "display_order": 1,
        }
        result = _format_attribute(row)
        assert result["value"] == 5000000.0
        assert result["attribute_type"] == "numeric"

    def test_boolean_attribute(self) -> None:
        row = {
            "id": "abc",
            "submission_id": "sub-1",
            "attribute_group": "cyber_risk",
            "attribute_name": "has_mfa",
            "attribute_type": "boolean",
            "numeric_value": None,
            "string_value": None,
            "boolean_value": True,
            "date_value": None,
            "display_order": 5,
        }
        result = _format_attribute(row)
        assert result["value"] is True

    def test_string_attribute(self) -> None:
        row = {
            "id": "abc",
            "submission_id": "sub-1",
            "attribute_group": "cyber_risk",
            "attribute_name": "industry_sic_code",
            "attribute_type": "string",
            "numeric_value": None,
            "string_value": "7372",
            "boolean_value": None,
            "date_value": None,
            "display_order": 3,
        }
        result = _format_attribute(row)
        assert result["value"] == "7372"

    def test_json_attribute(self) -> None:
        row = {
            "id": "abc",
            "submission_id": "sub-1",
            "attribute_group": "cyber_risk",
            "attribute_name": "tech_stack",
            "attribute_type": "json",
            "numeric_value": None,
            "string_value": '["Python", "React"]',
            "boolean_value": None,
            "date_value": None,
            "display_order": 13,
        }
        result = _format_attribute(row)
        assert result["value"] == ["Python", "React"]

    def test_submission_number_included_when_present(self) -> None:
        row = {
            "id": "abc",
            "submission_id": "sub-1",
            "attribute_group": "cyber_risk",
            "attribute_name": "annual_revenue",
            "attribute_type": "numeric",
            "numeric_value": 100,
            "string_value": None,
            "boolean_value": None,
            "date_value": None,
            "display_order": 1,
            "submission_number": "SUB-2026-ABCD",
        }
        result = _format_attribute(row)
        assert result["submission_number"] == "SUB-2026-ABCD"
