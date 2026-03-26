"""Regulatory filing API endpoints for OpenInsure.

Provides EU AI Act documentation generation (FRIA, transparency report,
technical documentation, conformity assessment), NAIC Schedule P export,
and bias alert threshold configuration.

All reports are generated from real platform data — decisions, audit events,
bias monitoring results, and actuarial data.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter()
_logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class FRIARequest(BaseModel):
    """Request to generate a Fundamental Rights Impact Assessment."""

    system_id: str | None = Field(
        None,
        description="Specific AI system ID to assess. If omitted, all systems are assessed.",
    )
    include_html: bool = Field(
        False,
        description="Include a PDF-ready HTML rendering of the FRIA.",
    )


class TransparencyReportRequest(BaseModel):
    """Request to generate an Art. 13 transparency report."""

    # No required fields — the report covers the full platform


class TechDocRequest(BaseModel):
    """Request to generate an Art. 11 technical documentation package."""


class BiasAlertConfigRequest(BaseModel):
    """Request to configure bias alert thresholds."""

    four_fifths_ratio: float = Field(
        0.8,
        ge=0.0,
        le=1.0,
        description="Adverse impact ratio threshold (default: 0.8 per 4/5ths rule).",
    )
    min_sample_size: int = Field(
        10,
        ge=1,
        description="Minimum group sample size for analysis.",
    )
    alert_on_single_group_flag: bool = Field(
        True,
        description="Alert when any single group is flagged.",
    )
    notification_channels: list[str] = Field(
        default_factory=lambda: ["platform"],
        description="Channels to send alerts to (e.g., platform, email, webhook).",
    )


class BiasAlertConfigResponse(BaseModel):
    """Current bias alert threshold configuration."""

    four_fifths_ratio: float
    min_sample_size: int
    alert_on_single_group_flag: bool
    notification_channels: list[str]
    updated_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/fria/generate", status_code=201)
async def generate_fria(body: FRIARequest | None = None) -> dict[str, Any]:
    """Generate a Fundamental Rights Impact Assessment (EU AI Act Art. 9).

    Queries all AI decisions, bias reports, escalations, and audit trail
    to produce a structured FRIA document with optional HTML rendering.
    """
    from openinsure.services.regulatory_filing import generate_fria as _generate_fria

    req = body or FRIARequest()
    result = await _generate_fria(
        system_id=req.system_id,
        include_html=req.include_html,
    )

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "compliance.fria_generated",
            "/compliance/fria/generate",
            {
                "fria_id": result.get("id", ""),
                "systems_assessed": len(
                    result.get("sections", {}).get("system_description", {}).get("systems_assessed", [])
                ),
            },
        )
    except Exception:
        _logger.debug("event.publish_skipped", event="compliance.fria_generated")

    return result


@router.post("/transparency-report", status_code=201)
async def generate_transparency_report(
    body: TransparencyReportRequest | None = None,
) -> dict[str, Any]:
    """Generate an Art. 13 transparency report.

    Documents how AI decisions are made, what data is used,
    confidence thresholds, agent architecture, and bias metrics.
    """
    from openinsure.services.regulatory_filing import generate_transparency_report as _generate

    result = await _generate()

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "compliance.transparency_report_generated",
            "/compliance/transparency-report",
            {"report_id": result.get("id", "")},
        )
    except Exception:
        _logger.debug("event.publish_skipped", event="compliance.transparency_report_generated")

    return result


@router.post("/tech-doc", status_code=201)
async def generate_tech_doc(body: TechDocRequest | None = None) -> dict[str, Any]:
    """Generate Art. 11 technical documentation package.

    Full system documentation: architecture, data flows, training data,
    validation approach, bias monitoring, and audit trail references.
    """
    from openinsure.services.regulatory_filing import generate_tech_doc as _generate

    result = await _generate()

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "compliance.tech_doc_generated",
            "/compliance/tech-doc",
            {"doc_id": result.get("id", "")},
        )
    except Exception:
        _logger.debug("event.publish_skipped", event="compliance.tech_doc_generated")

    return result


@router.get("/conformity-checklist")
async def get_conformity_checklist() -> dict[str, Any]:
    """Self-assessment conformity checklist against EU AI Act requirements.

    Returns per-article compliance status (compliant/partial/non_compliant)
    with evidence references from audit trails, bias reports, and decision records.
    """
    from openinsure.services.regulatory_filing import generate_conformity_checklist

    return await generate_conformity_checklist()


@router.get("/schedule-p")
async def get_schedule_p(
    lob: str | None = Query(None, description="Filter by line of business"),
) -> dict[str, Any]:
    """NAIC Schedule P loss development export.

    Generates loss development triangles by accident year from actual
    claims and policy data, in a format suitable for statutory reporting.
    """
    from openinsure.services.regulatory_filing import generate_schedule_p

    return await generate_schedule_p(lob=lob)


@router.post("/bias-alerts/configure", status_code=200)
async def configure_bias_alerts(body: BiasAlertConfigRequest) -> BiasAlertConfigResponse:
    """Configure automated bias alert thresholds.

    Sets thresholds for the 4/5ths rule, minimum sample sizes, and
    notification channels. Default: adverse impact ratio < 0.8 triggers alert.
    """
    from datetime import UTC, datetime

    from openinsure.services.regulatory_filing import set_bias_alert_config

    config = set_bias_alert_config(body.model_dump())
    return BiasAlertConfigResponse(
        **config,
        updated_at=datetime.now(UTC).isoformat(),
    )


@router.get("/bias-alerts/configure")
async def get_bias_alert_config() -> dict[str, Any]:
    """Retrieve current bias alert threshold configuration."""
    from openinsure.services.regulatory_filing import get_bias_alert_config as _get

    return _get()
