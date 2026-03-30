"""Risk Attribute Service — decomposes JSON risk data into typed, queryable rows.

On submission creation, decomposes ``risk_data`` / ``cyber_risk_data`` JSON
into individual ``risk_attributes`` rows with proper typing (string, numeric,
boolean, date).  The original JSON columns are preserved for backward
compatibility — risk_attributes is populated in parallel.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

logger = logging.getLogger(__name__)

# Maps known risk-data fields to their canonical type.
_FIELD_TYPES: dict[str, str] = {
    # Numeric fields
    "annual_revenue": "numeric",
    "employee_count": "numeric",
    "security_maturity_score": "numeric",
    "prior_incidents": "numeric",
    "prior_breach_costs": "numeric",
    "requested_limit": "numeric",
    "requested_deductible": "numeric",
    # Boolean fields
    "has_mfa": "boolean",
    "has_endpoint_protection": "boolean",
    "has_backup_strategy": "boolean",
    "has_incident_response_plan": "boolean",
    # String fields
    "industry_sic_code": "string",
    # JSON/array fields
    "tech_stack": "json",
}

# Display order for consistent presentation
_DISPLAY_ORDER: dict[str, int] = {
    "annual_revenue": 1,
    "employee_count": 2,
    "industry_sic_code": 3,
    "security_maturity_score": 4,
    "has_mfa": 5,
    "has_endpoint_protection": 6,
    "has_backup_strategy": 7,
    "has_incident_response_plan": 8,
    "prior_incidents": 9,
    "prior_breach_costs": 10,
    "requested_limit": 11,
    "requested_deductible": 12,
    "tech_stack": 13,
}


def _infer_type(value: Any) -> str:
    """Infer the attribute type from a Python value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "numeric"
    if isinstance(value, date):
        return "date"
    if isinstance(value, (list, dict)):
        return "json"
    # Try to parse as numeric
    if isinstance(value, str):
        try:
            Decimal(value)
            return "numeric"
        except (InvalidOperation, ValueError):
            pass
    return "string"


def decompose_risk_data(
    submission_id: str,
    risk_data: dict[str, Any],
    *,
    attribute_group: str = "cyber_risk",
) -> list[dict[str, Any]]:
    """Decompose a risk-data dict into a list of typed attribute rows.

    Returns a list of dicts ready for SQL insertion.
    """
    rows: list[dict[str, Any]] = []
    for key, value in risk_data.items():
        if value is None:
            continue

        attr_type = _FIELD_TYPES.get(key, _infer_type(value))
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "submission_id": submission_id,
            "attribute_group": attribute_group,
            "attribute_name": key,
            "attribute_type": attr_type,
            "string_value": None,
            "numeric_value": None,
            "boolean_value": None,
            "date_value": None,
            "display_order": _DISPLAY_ORDER.get(key, 99),
        }

        if attr_type == "numeric":
            try:
                row["numeric_value"] = float(Decimal(str(value)))
            except (InvalidOperation, ValueError):
                row["string_value"] = str(value)
                row["attribute_type"] = "string"
        elif attr_type == "boolean":
            row["boolean_value"] = bool(value)
        elif attr_type == "date":
            row["date_value"] = str(value)
        elif attr_type == "json":
            row["string_value"] = json.dumps(value) if not isinstance(value, str) else value
        else:
            row["string_value"] = str(value)

        rows.append(row)

    return rows


async def persist_risk_attributes(
    db: DatabaseAdapter,
    submission_id: str,
    risk_data: dict[str, Any],
    *,
    attribute_group: str = "cyber_risk",
) -> int:
    """Decompose and persist risk attributes for a submission.

    Uses MERGE-style upsert (DELETE + INSERT) to be idempotent.
    Returns the number of attributes persisted.
    """
    rows = decompose_risk_data(submission_id, risk_data, attribute_group=attribute_group)
    if not rows:
        return 0

    # Delete existing attributes for this submission+group to make it idempotent
    await db.execute_query(
        "DELETE FROM risk_attributes WHERE submission_id = ? AND attribute_group = ?",
        [submission_id, attribute_group],
    )

    for row in rows:
        await db.execute_query(
            """INSERT INTO risk_attributes
               (id, submission_id, attribute_group, attribute_name, attribute_type,
                string_value, numeric_value, boolean_value, date_value, display_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["id"],
                row["submission_id"],
                row["attribute_group"],
                row["attribute_name"],
                row["attribute_type"],
                row["string_value"],
                row["numeric_value"],
                row["boolean_value"],
                row["date_value"],
                row["display_order"],
            ],
        )

    logger.info(
        "Persisted %d risk attributes for submission %s (group=%s)",
        len(rows),
        submission_id,
        attribute_group,
    )
    return len(rows)


async def get_risk_attributes(
    db: DatabaseAdapter,
    submission_id: str,
) -> list[dict[str, Any]]:
    """Retrieve all risk attributes for a submission."""
    rows = await db.fetch_all(
        "SELECT * FROM risk_attributes WHERE submission_id = ? ORDER BY attribute_group, display_order",
        [submission_id],
    )
    return [_format_attribute(r) for r in rows]


async def query_risk_attributes(
    db: DatabaseAdapter,
    *,
    attribute_name: str | None = None,
    attribute_group: str | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    string_value: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Cross-submission query on risk attributes.

    Supports filtering by attribute name, group, numeric range, and string match.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if attribute_name:
        conditions.append("ra.attribute_name = ?")
        params.append(attribute_name)
    if attribute_group:
        conditions.append("ra.attribute_group = ?")
        params.append(attribute_group)
    if min_value is not None:
        conditions.append("ra.numeric_value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("ra.numeric_value <= ?")
        params.append(max_value)
    if string_value:
        conditions.append("ra.string_value LIKE ?")
        params.append(f"%{string_value}%")

    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT ra.*, s.submission_number
        FROM risk_attributes ra
        JOIN submissions s ON ra.submission_id = s.id
        WHERE {where}
        ORDER BY ra.attribute_name, ra.numeric_value DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """  # noqa: S608 — all user inputs are parameterised (?)
    params.extend([skip, limit])

    rows = await db.fetch_all(sql, params)
    return [_format_attribute(r) for r in rows]


def _format_attribute(row: dict[str, Any]) -> dict[str, Any]:
    """Format a raw SQL row into an API-friendly dict."""
    attr_type = row.get("attribute_type", "string")

    # Determine the effective value based on type
    if attr_type == "numeric":
        value = float(row["numeric_value"]) if row.get("numeric_value") is not None else None
    elif attr_type == "boolean":
        value = bool(row["boolean_value"]) if row.get("boolean_value") is not None else None
    elif attr_type == "date":
        val = row.get("date_value")
        value = val.isoformat() if hasattr(val, "isoformat") else str(val) if val else None
    elif attr_type == "json":
        raw = row.get("string_value", "")
        try:
            value = json.loads(raw) if raw else None
        except (json.JSONDecodeError, TypeError):
            value = raw
    else:
        value = row.get("string_value")

    result: dict[str, Any] = {
        "id": str(row.get("id", "")),
        "submission_id": str(row.get("submission_id", "")),
        "attribute_group": row.get("attribute_group", ""),
        "attribute_name": row.get("attribute_name", ""),
        "attribute_type": attr_type,
        "value": value,
        "display_order": row.get("display_order", 0),
    }

    # Include submission_number if available (from JOINed queries)
    if row.get("submission_number"):
        result["submission_number"] = str(row["submission_number"])

    return result
