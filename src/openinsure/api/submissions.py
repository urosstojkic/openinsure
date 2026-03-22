"""Submission API endpoints for OpenInsure.

Handles the full submission lifecycle: intake → triage → quote → bind.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_blob_storage, get_submission_repository
from openinsure.rbac.auth import CurrentUser, get_current_user
from openinsure.rbac.authority import AuthorityDecision, AuthorityEngine

router = APIRouter()
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_submission_repository()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_policy_data(
    submission: dict[str, Any],
    premium: float,
    *,
    policy_id: str | None = None,
    policy_number: str | None = None,
) -> dict[str, Any]:
    """Build a complete policy record from a submission.

    Ensures all business-required fields are populated:
    policyholder_name, coverages, effective/expiration dates, premium.
    """
    now = _now()
    pid = policy_id or str(uuid.uuid4())
    pnum = policy_number or f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    applicant = submission.get("applicant_name", "") or submission.get("insured_name", "Unknown Insured")
    lob = submission.get("line_of_business", "cyber")

    # Build default cyber coverages from the submission
    cyber_data = submission.get("cyber_risk_data", {})
    if isinstance(cyber_data, str):
        try:
            cyber_data = json.loads(cyber_data)
        except (json.JSONDecodeError, TypeError):
            cyber_data = {}

    limit = float(cyber_data.get("requested_limit", 1000000) if cyber_data else 1000000)
    deductible = float(cyber_data.get("requested_deductible", 10000) if cyber_data else 10000)

    coverages = [
        {
            "coverage_code": "BREACH-RESP",
            "coverage_name": "First-Party Breach Response",
            "limit": limit,
            "deductible": deductible,
            "premium": round(premium * 0.30, 2),
        },
        {
            "coverage_code": "THIRD-PARTY",
            "coverage_name": "Third-Party Liability",
            "limit": limit,
            "deductible": deductible,
            "premium": round(premium * 0.30, 2),
        },
        {
            "coverage_code": "REG-DEFENSE",
            "coverage_name": "Regulatory Defense & Penalties",
            "limit": limit * 0.5,
            "deductible": deductible,
            "premium": round(premium * 0.15, 2),
        },
        {
            "coverage_code": "BUS-INTERRUPT",
            "coverage_name": "Business Interruption",
            "limit": limit * 0.5,
            "deductible": deductible,
            "premium": round(premium * 0.15, 2),
        },
        {
            "coverage_code": "RANSOMWARE",
            "coverage_name": "Ransomware & Extortion",
            "limit": limit * 0.5,
            "deductible": deductible,
            "premium": round(premium * 0.10, 2),
        },
    ]

    return {
        "id": pid,
        "policy_number": pnum,
        "policyholder_name": applicant,
        "status": "active",
        "product_id": submission.get("product_id", f"{lob}-smb"),
        "submission_id": submission.get("id", ""),
        "insured_name": applicant,
        "effective_date": str(submission.get("requested_effective_date", now)),
        "expiration_date": str(submission.get("requested_expiration_date", now)),
        "premium": premium,
        "total_premium": premium,
        "written_premium": premium,
        "earned_premium": 0,
        "unearned_premium": premium,
        "coverages": coverages,
        "endorsements": [],
        "metadata": {"lob": lob, "source": "workflow"},
        "documents": [],
        "bound_at": now,
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubmissionStatus(StrEnum):
    """Lifecycle states for a submission.

    Must match the CHECK constraint in SQL schema (001_initial_schema.sql).
    """

    RECEIVED = "received"
    TRIAGING = "triaging"
    UNDERWRITING = "underwriting"
    QUOTED = "quoted"
    BOUND = "bound"
    DECLINED = "declined"
    EXPIRED = "expired"


class SubmissionChannel(StrEnum):
    """Intake channel for a submission."""

    PORTAL = "portal"
    API = "api"
    EMAIL = "email"
    BROKER = "broker"
    AGENT = "agent"


class LineOfBusiness(StrEnum):
    """Supported lines of business."""

    CYBER = "cyber"
    TECH_EO = "tech_eo"
    MPL = "mpl"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SubmissionCreate(BaseModel):
    """Payload for creating a new submission."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "applicant_name": "Acme Cyber Corp",
                    "applicant_email": "risk@acmecyber.com",
                    "channel": "api",
                    "line_of_business": "cyber",
                    "risk_data": {"annual_revenue": 5000000, "employee_count": 50, "industry": "Technology"},
                }
            ]
        }
    }

    applicant_name: str = Field(..., min_length=1, max_length=200)
    applicant_email: str | None = None
    status: SubmissionStatus | None = None
    channel: SubmissionChannel = SubmissionChannel.API
    line_of_business: LineOfBusiness = LineOfBusiness.CYBER
    risk_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubmissionUpdate(BaseModel):
    """Payload for updating an existing submission."""

    applicant_name: str | None = None
    applicant_email: str | None = None
    risk_data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class SubmissionResponse(BaseModel):
    """Public representation of a submission."""

    id: str = ""
    applicant_name: str = ""
    applicant_email: str | None = None
    status: str = "received"
    channel: str = "api"
    line_of_business: str = "cyber"
    lob: str = "cyber"
    risk_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    documents: list[str] = Field(default_factory=list)
    submission_number: str = ""
    quoted_premium: float | None = None
    requested_effective_date: str = ""
    requested_expiration_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    received_date: str = ""
    company_name: str = ""
    risk_score: float = 0
    priority: str = "medium"
    assigned_to: str | None = None
    decision_history: list[dict[str, Any]] = Field(default_factory=list)


class SubmissionList(BaseModel):
    """Paginated list of submissions."""

    items: list[SubmissionResponse]
    total: int
    skip: int
    limit: int


class TriageResult(BaseModel):
    """Result of AI-driven triage."""

    submission_id: str
    status: SubmissionStatus
    risk_score: float
    recommendation: str
    flags: list[str]


class QuoteResponse(BaseModel):
    """Generated quote details."""

    submission_id: str
    quote_id: str
    premium: float
    currency: str = "USD"
    coverages: list[dict[str, Any]]
    valid_until: str
    authority: dict[str, Any] | None = None


class BindResponse(BaseModel):
    """Result of binding a submission to a policy."""

    submission_id: str
    policy_id: str
    status: SubmissionStatus
    bound_at: str
    authority: dict[str, Any] | None = None


class DocumentUploadResponse(BaseModel):
    """Result of a document upload."""

    submission_id: str
    document_ids: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_submission(submission_id: str) -> dict[str, Any]:
    """Retrieve a submission or raise 404."""
    sub = await _repo.get_by_id(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")
    return sub


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=SubmissionResponse, status_code=201)
async def create_submission(body: SubmissionCreate) -> SubmissionResponse:
    """Create a new insurance submission.

    Accepts applicant information and risk data for a new insurance
    submission.  The submission enters the pipeline at **received** status
    and can be advanced through triage → quote → bind.

    Returns the created submission with a generated ID.
    """
    sid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": sid,
        "applicant_name": body.applicant_name,
        "applicant_email": body.applicant_email,
        "status": body.status or SubmissionStatus.RECEIVED,
        "channel": body.channel,
        "line_of_business": body.line_of_business,
        "risk_data": body.risk_data,
        "metadata": body.metadata,
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)
    return SubmissionResponse(**record)


@router.post("/acord-ingest", response_model=SubmissionResponse, status_code=201)
async def ingest_acord_xml(file: UploadFile = File(...)) -> SubmissionResponse:
    """Ingest an ACORD 125/126 XML application and create a submission.

    Accepts an XML file upload, parses the ACORD commercial insurance
    application form, and feeds the extracted data into the submission
    pipeline as a new submission with ``channel='api'`` and
    ``metadata.source='acord_xml'``.

    Addresses issue #38 (ACORD ingestion).
    """
    from openinsure.services.acord_parser import parse_acord_xml

    max_upload_size = 50 * 1024 * 1024  # 50 MB
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > max_upload_size:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    result = parse_acord_xml(content)
    if not result.applicant_name or result.applicant_name == "Unknown Applicant":
        if result.parse_warnings:
            raise HTTPException(
                status_code=422,
                detail=f"Could not extract applicant from ACORD XML: {'; '.join(result.parse_warnings)}",
            )

    payload = result.to_submission()

    sid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": sid,
        "applicant_name": payload["applicant_name"],
        "applicant_email": payload.get("applicant_email"),
        "status": SubmissionStatus.RECEIVED,
        "channel": "api",
        "line_of_business": payload.get("line_of_business", "cyber"),
        "risk_data": payload.get("risk_data", {}),
        "cyber_risk_data": payload.get("cyber_risk_data", {}),
        "metadata": payload.get("metadata", {}),
        "documents": [file.filename] if file.filename else [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)
    return SubmissionResponse(**record)


@router.get("", response_model=SubmissionList)
async def list_submissions(
    status: SubmissionStatus | None = Query(None, description="Filter by status"),
    channel: SubmissionChannel | None = Query(None, description="Filter by intake channel"),
    lob: LineOfBusiness | None = Query(None, alias="line_of_business", description="Filter by line of business"),
    created_after: str | None = Query(None, description="ISO-8601 date lower bound"),
    created_before: str | None = Query(None, description="ISO-8601 date upper bound"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> SubmissionList:
    """List submissions with optional filtering and pagination."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if channel is not None:
        filters["channel"] = channel
    if lob is not None:
        filters["line_of_business"] = lob
    if created_after is not None:
        filters["created_at_gte"] = created_after
    if created_before is not None:
        filters["created_at_lte"] = created_before

    total = await _repo.count(filters)
    page = await _repo.list_all(filters=filters, skip=skip, limit=limit)
    return SubmissionList(
        items=[SubmissionResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(submission_id: str) -> SubmissionResponse:
    """Retrieve a single submission by ID."""
    return SubmissionResponse(**await _get_submission(submission_id))


@router.put("/{submission_id}", response_model=SubmissionResponse)
async def update_submission(submission_id: str, body: SubmissionUpdate) -> SubmissionResponse:
    """Update a submission's mutable fields."""
    record = await _get_submission(submission_id)
    if record["status"] in {SubmissionStatus.BOUND, SubmissionStatus.DECLINED}:
        raise HTTPException(status_code=409, detail="Cannot update a submission that is bound or declined")

    updates = body.model_dump(exclude_unset=True)
    if "risk_data" in updates and updates["risk_data"] is not None:
        record["risk_data"].update(updates.pop("risk_data"))
        updates["risk_data"] = record["risk_data"]
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
        updates["metadata"] = record["metadata"]
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    await _repo.update(submission_id, updates)
    return SubmissionResponse(**record)


@router.post("/{submission_id}/triage", response_model=TriageResult)
async def triage_submission(submission_id: str) -> TriageResult:
    """Trigger AI-powered triage on a submission.

    Calls the Foundry triage agent to assess risk appetite, assign a risk
    score, and recommend next steps.  Falls back to deterministic local
    logic when Foundry is unavailable.

    Advances the submission from **received** → **underwriting**.
    """
    from openinsure.agents.foundry_client import get_foundry_client

    record = await _get_submission(submission_id)
    if record["status"] not in {SubmissionStatus.RECEIVED, SubmissionStatus.TRIAGING}:
        raise HTTPException(status_code=409, detail="Submission is not in a triageable state")

    foundry = get_foundry_client()

    if foundry.is_available:
        result = await foundry.invoke(
            "openinsure-submission",
            "You are triaging a cyber insurance submission. Our appetite accepts:\n"
            "- IT/Tech (SIC 7xxx), Financial (SIC 6xxx), Professional Services\n"
            "- Revenue $500K to $50M\n"
            "- Security maturity score 4+ out of 10\n"
            "- Max 3 prior incidents\n\n"
            "Respond ONLY with JSON:\n"
            '{"appetite_match": "yes", "risk_score": 5, "priority": "medium", '
            '"confidence": 0.9, "reasoning": "..."}\n\n'
            f"Submission:\n{json.dumps(record, default=str)[:1000]}",
        )
        resp = result.get("response", {})
        if isinstance(resp, dict) and result.get("source") == "foundry":
            record["status"] = SubmissionStatus.UNDERWRITING
            record["triage_result"] = resp
            record["updated_at"] = _now()
            await _repo.update(
                submission_id,
                {"status": "underwriting", "triage_result": json.dumps(resp), "updated_at": record["updated_at"]},
            )

            # Record triage decision
            try:
                from openinsure.infrastructure.factory import get_compliance_repository

                compliance_repo = get_compliance_repository()
                await compliance_repo.store_decision(
                    {
                        "decision_id": str(uuid.uuid4()),
                        "agent_id": "openinsure-submission",
                        "decision_type": "triage",
                        "entity_id": submission_id,
                        "entity_type": "submission",
                        "confidence": float(resp.get("confidence", 0.85)),
                        "input_summary": {"submission_id": submission_id},
                        "output": resp,
                        "reasoning": str(resp.get("reasoning", "")),
                        "model_used": "gpt-5.1",
                        "human_oversight": "recommended",
                        "created_at": _now(),
                    }
                )
            except Exception:
                _logger.warning(
                    "submissions.decision_recording_failed",
                    decision_type="triage",
                    submission_id=submission_id,
                    exc_info=True,
                )

            from openinsure.services.event_publisher import publish_domain_event

            await publish_domain_event(
                "submission.triaged",
                f"/submissions/{submission_id}",
                {"submission_id": submission_id},
            )
            appetite = str(resp.get("appetite_match", "yes")).lower()
            recommendation = "decline" if appetite in ("no", "decline") else "proceed_to_quote"
            flags: list[str] = []
            if resp.get("reasoning"):
                flags.append(str(resp["reasoning"]))
            return TriageResult(
                submission_id=submission_id,
                status=SubmissionStatus.UNDERWRITING,
                risk_score=float(resp.get("risk_score", 5)),
                recommendation=recommendation,
                flags=flags,
            )

    # Local fallback
    record["status"] = SubmissionStatus.UNDERWRITING
    record["updated_at"] = _now()
    fallback_triage = json.dumps({"risk_score": 0.42, "recommendation": "proceed_to_quote", "source": "local"})
    await _repo.update(
        submission_id, {"status": "underwriting", "triage_result": fallback_triage, "updated_at": record["updated_at"]}
    )

    return TriageResult(
        submission_id=submission_id,
        status=SubmissionStatus.UNDERWRITING,
        risk_score=0.42,
        recommendation="proceed_to_quote",
        flags=[],
    )


@router.post("/{submission_id}/quote", response_model=QuoteResponse)
async def generate_quote(submission_id: str, user: CurrentUser = Depends(get_current_user)) -> QuoteResponse:
    """Generate a quote for the submission.

    Calls the Foundry underwriting agent when available, falling back to
    deterministic local logic.
    """
    from openinsure.agents.foundry_client import get_foundry_client

    record = await _get_submission(submission_id)
    if record["status"] not in {SubmissionStatus.UNDERWRITING, SubmissionStatus.UNDERWRITING}:
        raise HTTPException(status_code=409, detail="Submission must be triaged before quoting")

    foundry = get_foundry_client()

    if foundry.is_available:
        result = await foundry.invoke(
            "openinsure-underwriting",
            "Price this cyber insurance submission. Calculate premium.\n"
            "Base: $1.50 per $1000 revenue. Adjust for industry, security, incidents.\n"
            "Respond ONLY with JSON:\n"
            '{"risk_score": 35, "recommended_premium": 12500, "confidence": 0.85}\n\n'
            f"Submission:\n{json.dumps(record, default=str)[:800]}",
        )
        resp = result.get("response", {})
        if isinstance(resp, dict) and "recommended_premium" in resp:
            raw_premium = resp["recommended_premium"]
            premium = float(raw_premium) if raw_premium is not None else 5000.0
            premium = premium or 5000.0  # fallback if agent returns 0
            record["status"] = SubmissionStatus.QUOTED
            record["quoted_premium"] = premium
            record["updated_at"] = _now()
            await _repo.update(
                submission_id, {"status": "quoted", "quoted_premium": premium, "updated_at": record["updated_at"]}
            )

            # Record underwriting/quote decision
            try:
                from openinsure.infrastructure.factory import get_compliance_repository

                compliance_repo = get_compliance_repository()
                await compliance_repo.store_decision(
                    {
                        "decision_id": str(uuid.uuid4()),
                        "agent_id": "openinsure-underwriting",
                        "decision_type": "underwriting",
                        "entity_id": submission_id,
                        "entity_type": "submission",
                        "confidence": float(resp.get("confidence", 0.85)),
                        "input_summary": {"submission_id": submission_id},
                        "output": resp,
                        "reasoning": str(resp.get("reasoning", "")),
                        "model_used": "gpt-5.1",
                        "human_oversight": "recommended",
                        "created_at": _now(),
                    }
                )
            except Exception:
                _logger.warning(
                    "submissions.decision_recording_failed",
                    decision_type="quote",
                    submission_id=submission_id,
                    exc_info=True,
                )

            from openinsure.services.event_publisher import publish_domain_event

            # Authority check
            engine = AuthorityEngine()
            user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
            auth_result = engine.check_quote_authority(Decimal(str(premium)), user_role)
            if auth_result.decision == AuthorityDecision.ESCALATE:
                from starlette.responses import JSONResponse

                from openinsure.services.escalation import escalate

                esc = await escalate(
                    action="quote",
                    entity_type="submission",
                    entity_id=submission_id,
                    requested_by=user.display_name,
                    requested_role=user_role,
                    amount=float(premium),
                    authority_result={
                        "required_role": auth_result.required_role,
                        "escalation_chain": auth_result.escalation_chain,
                        "reason": auth_result.reason,
                    },
                )
                return JSONResponse(  # type: ignore[return-value]
                    status_code=202,
                    content={
                        "status": "escalated",
                        "escalation_id": esc["id"],
                        "reason": auth_result.reason,
                        "required_role": auth_result.required_role,
                        "message": f"Action requires approval from {auth_result.required_role}",
                    },
                )
            await publish_domain_event(
                "authority.checked",
                f"/submissions/{submission_id}",
                {
                    "action": "quote",
                    "amount": str(premium),
                    "user_role": user_role,
                    "decision": auth_result.decision,
                    "reason": auth_result.reason,
                },
            )

            await publish_domain_event(
                "submission.quoted",
                f"/submissions/{submission_id}",
                {"submission_id": submission_id, "premium": premium},
            )
            return QuoteResponse(
                submission_id=submission_id,
                quote_id=str(uuid.uuid4()),
                premium=premium,
                currency="USD",
                coverages=[{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
                valid_until=_now(),
                authority={"decision": auth_result.decision, "reason": auth_result.reason},
            )

    # Local fallback
    premium = 5000.00
    record["status"] = SubmissionStatus.QUOTED
    record["updated_at"] = _now()
    await _repo.update(
        submission_id, {"status": "quoted", "quoted_premium": premium, "updated_at": record["updated_at"]}
    )
    valid_until = datetime(2099, 12, 31, tzinfo=UTC).isoformat()

    # Authority check
    from openinsure.services.event_publisher import publish_domain_event

    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    auth_result = engine.check_quote_authority(Decimal(str(premium)), user_role)
    if auth_result.decision == AuthorityDecision.ESCALATE:
        from starlette.responses import JSONResponse

        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="quote",
            entity_type="submission",
            entity_id=submission_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(premium),
            authority_result={
                "required_role": auth_result.required_role,
                "escalation_chain": auth_result.escalation_chain,
                "reason": auth_result.reason,
            },
        )
        return JSONResponse(  # type: ignore[return-value]
            status_code=202,
            content={
                "status": "escalated",
                "escalation_id": esc["id"],
                "reason": auth_result.reason,
                "required_role": auth_result.required_role,
                "message": f"Action requires approval from {auth_result.required_role}",
            },
        )
    await publish_domain_event(
        "authority.checked",
        f"/submissions/{submission_id}",
        {
            "action": "quote",
            "amount": str(premium),
            "user_role": user_role,
            "decision": auth_result.decision,
            "reason": auth_result.reason,
        },
    )

    return QuoteResponse(
        submission_id=submission_id,
        quote_id=str(uuid.uuid4()),
        premium=premium,
        currency="USD",
        coverages=[{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
        valid_until=valid_until,
        authority={"decision": auth_result.decision, "reason": auth_result.reason},
    )


@router.post("/{submission_id}/bind", response_model=BindResponse)
async def bind_submission(submission_id: str, user: CurrentUser = Depends(get_current_user)) -> BindResponse:
    """Bind the submission, creating a real policy and billing account."""
    from openinsure.infrastructure.factory import get_billing_repository, get_policy_repository
    from openinsure.services.event_publisher import publish_domain_event

    record = await _get_submission(submission_id)
    if record["status"] != SubmissionStatus.QUOTED:
        raise HTTPException(status_code=409, detail="Submission must be quoted before binding")

    now = _now()
    policy_id = str(uuid.uuid4())
    policy_number = f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    premium = record.get("quoted_premium", 0) or record.get("total_premium", 10000)

    # Authority check before binding
    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    cyber_data = record.get("risk_data", {})
    if isinstance(cyber_data, str):
        try:
            cyber_data = json.loads(cyber_data)
        except (json.JSONDecodeError, TypeError):
            cyber_data = {}
    limit = Decimal(str(cyber_data.get("requested_limit", 1000000) if cyber_data else 1000000))
    auth_result = engine.check_bind_authority(Decimal(str(premium)), user_role, limit)
    if auth_result.decision == AuthorityDecision.ESCALATE:
        from starlette.responses import JSONResponse

        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="bind",
            entity_type="submission",
            entity_id=submission_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(premium),
            authority_result={
                "required_role": auth_result.required_role,
                "escalation_chain": auth_result.escalation_chain,
                "reason": auth_result.reason,
            },
        )
        return JSONResponse(  # type: ignore[return-value]
            status_code=202,
            content={
                "status": "escalated",
                "escalation_id": esc["id"],
                "reason": auth_result.reason,
                "required_role": auth_result.required_role,
                "message": f"Action requires approval from {auth_result.required_role}",
            },
        )
    # Create the actual policy record
    policy_repo = get_policy_repository()
    policy_data = _build_policy_data(record, premium, policy_id=policy_id, policy_number=policy_number)

    # Invoke Foundry policy agent for issuance review
    from openinsure.agents.foundry_client import get_foundry_client

    foundry = get_foundry_client()
    if foundry.is_available:
        policy_review = await foundry.invoke(
            "openinsure-policy",
            "Review and approve this policy for issuance. Verify coverages, "
            "terms, and pricing are appropriate.\n"
            'Respond with JSON: {"recommendation": "issue", "terms_complete": true, '
            '"notes": "...", "confidence": 0.9}\n\n'
            f"Submission: {json.dumps(record, default=str)[:600]}\n"
            f"Premium: {premium}\nPolicy: {policy_number}",
        )
        from openinsure.services.event_publisher import publish_domain_event as _pub

        await _pub(
            "policy.ai_review",
            f"/policies/{policy_id}",
            {
                "policy_id": policy_id,
                "source": policy_review.get("source", "unknown"),
                "recommendation": policy_review.get("response", {}).get("recommendation")
                if isinstance(policy_review.get("response"), dict)
                else None,
            },
        )

        # Record policy review decision
        try:
            from openinsure.infrastructure.factory import get_compliance_repository

            compliance_repo = get_compliance_repository()
            pr_resp = policy_review.get("response", {})
            await compliance_repo.store_decision(
                {
                    "decision_id": str(uuid.uuid4()),
                    "agent_id": "openinsure-policy",
                    "decision_type": "policy_review",
                    "entity_id": submission_id,
                    "entity_type": "submission",
                    "confidence": float(pr_resp.get("confidence", 0.9)) if isinstance(pr_resp, dict) else 0.9,
                    "input_summary": {"submission_id": submission_id, "policy_number": policy_number},
                    "output": pr_resp if isinstance(pr_resp, dict) else {"raw": str(pr_resp)[:500]},
                    "reasoning": str(pr_resp.get("notes", "")) if isinstance(pr_resp, dict) else "",
                    "model_used": "gpt-5.1",
                    "human_oversight": "recommended",
                    "created_at": _now(),
                }
            )
        except Exception:
            _logger.warning(
                "submissions.decision_recording_failed",
                decision_type="bind",
                submission_id=submission_id,
                exc_info=True,
            )

    await policy_repo.create(policy_data)

    # Create billing account
    billing_repo = get_billing_repository()
    billing_data = {
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "billing_plan": "direct_bill",
        "total_premium": premium,
        "balance_due": premium,
        "created_at": now,
        "updated_at": now,
    }
    await billing_repo.create(billing_data)

    # Update submission status
    record["status"] = SubmissionStatus.BOUND
    record["updated_at"] = now
    await _repo.update(submission_id, {"status": "bound", "updated_at": now})

    # Publish domain events
    await publish_domain_event(
        "authority.checked",
        f"/submissions/{submission_id}",
        {
            "action": "bind",
            "amount": str(premium),
            "user_role": user_role,
            "decision": auth_result.decision,
            "reason": auth_result.reason,
        },
    )
    await publish_domain_event(
        event_type="policy.bound",
        subject=f"/policies/{policy_id}",
        data={
            "policy_id": policy_id,
            "policy_number": policy_number,
            "premium": str(premium),
            "submission_id": submission_id,
        },
    )

    return BindResponse(
        submission_id=submission_id,
        policy_id=policy_id,
        status=SubmissionStatus.BOUND,
        bound_at=now,
        authority={"decision": auth_result.decision, "reason": auth_result.reason},
    )


@router.post("/{submission_id}/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    submission_id: str,
    files: list[UploadFile] = File(...),
) -> DocumentUploadResponse:
    """Upload one or more documents to a submission."""
    record = await _get_submission(submission_id)
    storage = get_blob_storage()
    doc_ids: list[str] = []
    for f in files:
        doc_id = str(uuid.uuid4())
        doc_ids.append(doc_id)
        record["documents"].append(doc_id)

        max_upload_size = 50 * 1024 * 1024  # 50 MB
        content = await f.read()
        if len(content) > max_upload_size:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
        if storage:
            blob_name = f"submission/{submission_id}/{doc_id}/{f.filename}"
            await storage.upload_document(
                blob_name=blob_name,
                data=content,
                content_type=f.content_type or "application/octet-stream",
                metadata={
                    "submission_id": submission_id,
                    "document_id": doc_id,
                    "original_filename": f.filename or "",
                },
            )

    record["updated_at"] = _now()
    return DocumentUploadResponse(submission_id=submission_id, document_ids=doc_ids)


@router.post("/{submission_id}/process")
async def process_submission(submission_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, object]:
    """Run the full multi-agent new business workflow via the workflow engine.

    Delegates agent orchestration (triage → underwriting → compliance) to
    :func:`execute_workflow`, then applies business logic (authority checks,
    policy creation, billing) based on the workflow results.
    """
    from openinsure.infrastructure.factory import (
        get_billing_repository,
        get_compliance_repository,
        get_policy_repository,
    )
    from openinsure.services.event_publisher import publish_domain_event
    from openinsure.services.workflow_engine import execute_workflow

    submission = await _repo.get_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # --- Run multi-agent workflow ---
    execution = await execute_workflow("new_business", submission_id, "submission", submission)

    now = _now()
    results: dict[str, Any] = {s["name"]: s for s in execution.steps_completed}

    # --- Interpret triage result ---
    intake_step = results.get("intake", {})
    triage_resp = intake_step.get("response", {})
    appetite = "yes"
    if isinstance(triage_resp, dict):
        match_val = str(triage_resp.get("appetite_match", "yes")).lower().strip()
        appetite = "no" if match_val in ("no", "decline", "false", "reject", "outside") else "yes"
    elif isinstance(triage_resp, str):
        appetite = "no" if any(w in triage_resp.lower() for w in ["decline", "reject", "outside appetite"]) else "yes"

    await _repo.update(
        submission_id,
        {
            "status": "underwriting",
            "triage_result": json.dumps(triage_resp) if isinstance(triage_resp, dict) else str(triage_resp),
            "updated_at": now,
        },
    )
    await publish_domain_event("submission.triaged", f"/submissions/{submission_id}", {"submission_id": submission_id})

    # Early decline if outside appetite
    if appetite in ("no", "decline", "false"):
        await _repo.update(submission_id, {"status": "declined", "updated_at": now})
        await publish_domain_event(
            "submission.declined",
            f"/submissions/{submission_id}",
            {"submission_id": submission_id, "reason": "outside_appetite"},
        )
        return json.loads(
            json.dumps(
                {
                    "submission_id": submission_id,
                    "workflow": "new_business",
                    "workflow_id": execution.id,
                    "outcome": "declined",
                    "reason": "outside_appetite",
                    "policy_id": None,
                    "policy_number": None,
                    "premium": None,
                    "steps": results,
                    "authority": {
                        "decision": "auto_execute",
                        "reason": "Declined at triage; no bind authority required",
                    },
                },
                default=str,
            )
        )

    # --- Extract underwriting premium ---
    uw_step = results.get("underwriting", {})
    uw_resp = uw_step.get("response", {})
    premium: float = 10000  # fallback
    if isinstance(uw_resp, dict):
        premium = float(uw_resp.get("recommended_premium", uw_resp.get("premium", 10000)) or 10000)
    await _repo.update(
        submission_id,
        {
            "status": "quoted",
            "quoted_premium": premium,
            "triage_result": json.dumps(triage_resp) if isinstance(triage_resp, dict) else str(triage_resp),
            "updated_at": now,
        },
    )
    await publish_domain_event(
        "submission.quoted", f"/submissions/{submission_id}", {"submission_id": submission_id, "premium": premium}
    )

    # --- Authority check & auto-bind ---
    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    cyber_data = submission.get("cyber_risk_data", submission.get("risk_data", {}))
    if isinstance(cyber_data, str):
        try:
            cyber_data = json.loads(cyber_data)
        except (json.JSONDecodeError, TypeError):
            cyber_data = {}
    bind_limit = Decimal(str(cyber_data.get("requested_limit", 1000000) if cyber_data else 1000000))
    bind_auth = engine.check_bind_authority(Decimal(str(premium)), user_role, bind_limit)
    await publish_domain_event(
        "authority.checked",
        f"/submissions/{submission_id}",
        {
            "action": "bind",
            "amount": str(premium),
            "user_role": user_role,
            "decision": bind_auth.decision,
            "reason": bind_auth.reason,
        },
    )
    policy_id = None
    policy_number = None
    escalation_id = None
    if bind_auth.decision == AuthorityDecision.ESCALATE:
        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="bind",
            entity_type="submission",
            entity_id=submission_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(premium),
            authority_result={
                "required_role": bind_auth.required_role,
                "escalation_chain": bind_auth.escalation_chain,
                "reason": bind_auth.reason,
            },
        )
        escalation_id = esc["id"]
    else:
        policy_id = str(uuid.uuid4())
        policy_number = f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        policy_repo = get_policy_repository()
        policy_data = _build_policy_data(submission, premium, policy_id=policy_id, policy_number=policy_number)
        await policy_repo.create(policy_data)

        billing_repo = get_billing_repository()
        await billing_repo.create(
            {
                "id": str(uuid.uuid4()),
                "policy_id": policy_id,
                "billing_plan": "direct_bill",
                "total_premium": premium,
                "balance_due": premium,
                "created_at": now,
                "updated_at": now,
            }
        )

        await _repo.update(submission_id, {"status": "bound", "updated_at": now})
        await publish_domain_event(
            "policy.bound",
            f"/policies/{policy_id}",
            {
                "policy_id": policy_id,
                "policy_number": policy_number,
                "premium": premium,
                "submission_id": submission_id,
            },
        )

    # --- Store compliance decision ---
    compliance_repo = get_compliance_repository()
    if compliance_repo:
        await compliance_repo.store_decision(
            {
                "decision_id": str(uuid.uuid4()),
                "agent_id": "openinsure-orchestrator",
                "decision_type": "new_business_workflow",
                "input_summary": {"submission_id": submission_id},
                "output": {"premium": premium, "policy_id": policy_id, "outcome": "bound" if policy_id else "quoted"},
                "confidence": float(uw_resp.get("confidence", 0.8)) if isinstance(uw_resp, dict) else 0.8,
                "model_used": "gpt-5.1",
            }
        )

    outcome = "bound" if policy_id else "quoted_pending_approval"
    result: dict[str, Any] = {
        "submission_id": submission_id,
        "workflow": "new_business",
        "workflow_id": execution.id,
        "outcome": outcome,
        "policy_id": policy_id,
        "policy_number": policy_number,
        "premium": premium,
        "escalation_id": escalation_id,
        "steps": results,
        "authority": {
            "decision": bind_auth.decision,
            "reason": bind_auth.reason,
        },
    }
    return json.loads(json.dumps(result, default=str))
