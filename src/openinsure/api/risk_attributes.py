"""Risk Attributes API endpoints for OpenInsure.

Provides endpoints for querying typed risk attributes decomposed from
submission JSON data (#172).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from openinsure.infrastructure.factory import get_database_adapter, get_submission_repository

router = APIRouter()
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RiskAttributeResponse(BaseModel):
    """A single typed risk attribute."""

    id: str = ""
    submission_id: str = ""
    attribute_group: str = ""
    attribute_name: str = ""
    attribute_type: str = ""
    value: Any = None
    display_order: int = 0
    submission_number: str | None = None


class RiskAttributeList(BaseModel):
    """List of risk attributes."""

    items: list[RiskAttributeResponse]
    total: int
    skip: int = 0
    limit: int = 50


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/risk-attributes",
    response_model=RiskAttributeList,
    tags=["risk-attributes"],
)
async def get_submission_risk_attributes(submission_id: str) -> RiskAttributeList:
    """Retrieve all typed risk attributes for a submission."""
    # Verify submission exists
    sub_repo = get_submission_repository()
    submission = await sub_repo.get_by_id(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

    db = get_database_adapter()
    if db is None:
        # In-memory mode: decompose from the submission's risk_data on the fly
        from openinsure.services.risk_attribute_service import decompose_risk_data

        risk_data = submission.get("risk_data") or submission.get("cyber_risk_data") or {}
        if isinstance(risk_data, str):
            import json

            try:
                risk_data = json.loads(risk_data)
            except (json.JSONDecodeError, TypeError):
                risk_data = {}

        items = decompose_risk_data(submission_id, risk_data)
        # Format for response
        formatted = []
        for item in items:
            attr_type = item["attribute_type"]
            if attr_type == "numeric":
                value = item["numeric_value"]
            elif attr_type == "boolean":
                value = item["boolean_value"]
            else:
                value = item["string_value"]
            formatted.append(
                RiskAttributeResponse(
                    id=item["id"],
                    submission_id=item["submission_id"],
                    attribute_group=item["attribute_group"],
                    attribute_name=item["attribute_name"],
                    attribute_type=attr_type,
                    value=value,
                    display_order=item["display_order"],
                )
            )
        return RiskAttributeList(items=formatted, total=len(formatted))

    from openinsure.services.risk_attribute_service import get_risk_attributes

    attrs = await get_risk_attributes(db, submission_id)
    return RiskAttributeList(
        items=[RiskAttributeResponse(**a) for a in attrs],
        total=len(attrs),
    )


@router.get(
    "/analytics/risk-attributes",
    response_model=RiskAttributeList,
    tags=["risk-attributes", "analytics"],
)
async def query_risk_attributes_analytics(
    attribute_name: str | None = Query(None, description="Filter by attribute name (e.g., annual_revenue)"),
    attribute_group: str | None = Query(None, description="Filter by attribute group (e.g., cyber_risk)"),
    min: float | None = Query(None, description="Minimum numeric value (inclusive)", alias="min"),
    max: float | None = Query(None, description="Maximum numeric value (inclusive)", alias="max"),
    string_value: str | None = Query(None, description="Substring match on string values"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> RiskAttributeList:
    """Cross-submission analytics query on typed risk attributes.

    Enables queries like: 'Find all submissions with annual_revenue > $1M'.
    """
    db = get_database_adapter()
    if db is None:
        # In-memory mode: no cross-submission query support
        return RiskAttributeList(items=[], total=0)

    from openinsure.services.risk_attribute_service import query_risk_attributes

    attrs = await query_risk_attributes(
        db,
        attribute_name=attribute_name,
        attribute_group=attribute_group,
        min_value=min,
        max_value=max,
        string_value=string_value,
        skip=skip,
        limit=limit,
    )
    return RiskAttributeList(
        items=[RiskAttributeResponse(**a) for a in attrs],
        total=len(attrs),
    )
