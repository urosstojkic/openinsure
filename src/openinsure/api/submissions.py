"""Submission API endpoints for OpenInsure.

Handles the full submission lifecycle: intake → triage → quote → bind.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from openinsure.domain.exceptions import SubmissionNotFoundError
from openinsure.infrastructure.factory import get_audit_service, get_blob_storage, get_submission_repository
from openinsure.rate_limit import limiter
from openinsure.rbac.auth import CurrentUser, get_current_user
from openinsure.services.party_resolution import get_party_resolution_service

router = APIRouter()
_logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_submission_repository()


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
    REFERRED = "referred"
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
    COMMERCIAL_PROPERTY = "commercial_property"


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
    cyber_risk_data: dict[str, Any] = Field(default_factory=dict)
    effective_date: str | None = None
    expiration_date: str | None = None
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
    subjectivities: list[dict[str, Any]] = Field(default_factory=list)
    referral_reason: str | None = None
    declination_reason: str | None = None


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
    rating_breakdown: dict[str, Any] | None = None


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
    """Retrieve a submission or raise SubmissionNotFoundError."""
    sub = await _repo.get_by_id(submission_id)
    if sub is None:
        raise SubmissionNotFoundError(submission_id)

    # Populate decision_history from audit trail (change_log)
    try:
        audit = get_audit_service()
        history = await audit.get_history("submission", submission_id)
        if history:
            sub["decision_history"] = [
                {
                    "id": h.get("id", ""),
                    "timestamp": h.get("changed_at", ""),
                    "actor": h.get("changed_by", "system"),
                    "action": (h.get("changes") or {}).get("_original_action", h.get("action", "")),
                    "details": _format_decision_details(h),
                    "is_agent": h.get("changed_by", "") in ("ai-agent", "system", "triage-agent", "underwriting-agent"),
                }
                for h in history
            ]
    except Exception:
        pass  # fail-open: decision_history stays empty

    return sub


def _format_decision_details(audit_entry: dict[str, Any]) -> str:
    """Build a human-readable summary from an audit change_log entry."""
    changes = audit_entry.get("changes") or {}
    action = changes.get("_original_action", audit_entry.get("action", ""))
    parts: list[str] = []
    if action == "triage":
        score = changes.get("risk_score")
        rec = changes.get("recommendation", "")
        if score is not None:
            parts.append(f"Risk score: {score}")
        if rec:
            parts.append(f"Recommendation: {rec}")
    elif action in ("quote", "update") and changes.get("premium"):
        parts.append(f"Premium: ${changes['premium']:,.0f}" if isinstance(changes["premium"], (int, float)) else f"Premium: {changes['premium']}")
    elif action == "bind":
        pid = changes.get("policy_id", "")
        if pid:
            parts.append(f"Policy: {pid}")
    elif action == "create":
        name = changes.get("applicant_name", "")
        if name:
            parts.append(f"Applicant: {name}")
    if not parts:
        # Generic fallback
        safe_keys = {"status", "risk_score", "recommendation", "premium", "policy_id"}
        parts = [f"{k}: {v}" for k, v in changes.items() if k in safe_keys and v]
    return "; ".join(parts) if parts else action


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SubmissionResponse,
    status_code=201,
    summary="Create submission",
    description="Accepts applicant information and risk data for a new insurance "
    "submission. The submission enters the pipeline at **received** status "
    "and can be advanced through triage → quote → bind.",
    openapi_extra={
        "x-openapi-examples": {
            "cyber_small_business": {
                "summary": "Small business cyber submission",
                "value": {
                    "applicant_name": "Acme Cyber Corp",
                    "applicant_email": "risk@acmecyber.com",
                    "channel": "api",
                    "line_of_business": "cyber",
                    "risk_data": {
                        "annual_revenue": 5000000,
                        "employee_count": 50,
                        "industry": "Technology",
                        "security_maturity_score": 7,
                    },
                },
            },
            "cyber_enterprise": {
                "summary": "Enterprise cyber submission",
                "value": {
                    "applicant_name": "GlobalTech Holdings",
                    "applicant_email": "underwriting@globaltech.com",
                    "channel": "broker",
                    "line_of_business": "cyber",
                    "risk_data": {
                        "annual_revenue": 500000000,
                        "employee_count": 5000,
                        "industry": "Financial Services",
                        "security_maturity_score": 9,
                        "has_mfa": True,
                        "has_endpoint_protection": True,
                    },
                },
            },
        }
    },
)
async def create_submission(body: SubmissionCreate) -> SubmissionResponse:
    """Create a new insurance submission.

    Accepts applicant information and risk data for a new insurance
    submission.  The submission enters the pipeline at **received** status
    and can be advanced through triage → quote → bind.

    Returns the created submission with a generated ID.
    """
    sid = str(uuid.uuid4())
    now = _now()
    # Merge cyber_risk_data into risk_data (both accepted)
    merged_risk = {**body.risk_data, **body.cyber_risk_data}

    # Resolve applicant to a party record (deduplication)
    party_svc = get_party_resolution_service()
    applicant_data: dict[str, Any] = {"name": body.applicant_name}
    if body.applicant_email:
        applicant_data["contacts"] = [
            {"contact_type": "primary", "name": body.applicant_name, "email": body.applicant_email}
        ]
    party_id = await party_svc.resolve_or_create(applicant_data)

    record: dict[str, Any] = {
        "id": sid,
        "applicant_name": body.applicant_name,
        "applicant_email": body.applicant_email,
        "applicant_id": party_id,
        "status": body.status or SubmissionStatus.RECEIVED,
        "channel": body.channel,
        "line_of_business": body.line_of_business,
        "risk_data": merged_risk,
        "cyber_risk_data": merged_risk,
        "effective_date": body.effective_date or "",
        "expiration_date": body.expiration_date or "",
        "metadata": body.metadata,
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)

    # Audit trail
    audit = get_audit_service()
    await audit.log_change(
        "submission",
        sid,
        "create",
        body.applicant_name or "system",
        changes={
            "applicant_name": body.applicant_name,
            "line_of_business": body.line_of_business,
            "channel": body.channel,
        },
    )

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


@router.get(
    "",
    response_model=SubmissionList,
    summary="List submissions",
    description="List submissions with optional filtering by status, channel, "
    "line of business, and date range. Returns paginated results.",
)
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


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get submission",
    description="Retrieve a single submission by its unique ID.",
)
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

    # Audit trail
    audit = get_audit_service()
    await audit.log_change("submission", submission_id, "update", "system", changes=updates)

    return SubmissionResponse(**record)


@router.post(
    "/{submission_id}/triage",
    response_model=TriageResult,
    summary="Triage submission",
    description="Trigger AI-powered triage on a submission. Uses the Foundry triage "
    "agent to assess risk appetite, assign a risk score, and recommend "
    "whether to proceed to quoting or decline. Advances the submission "
    "from **received** → **underwriting**.",
)
@limiter.limit("20/minute")
async def triage_submission(request: Request, submission_id: str) -> TriageResult:
    """Trigger AI-powered triage on a submission.

    Advances the submission from **received** → **underwriting**.
    """
    record = await _get_submission(submission_id)
    if record["status"] not in {SubmissionStatus.RECEIVED, SubmissionStatus.TRIAGING}:
        raise HTTPException(status_code=409, detail="Submission is not in a triageable state")

    from openinsure.services.submission_service import SubmissionService

    svc = SubmissionService()
    result = await svc.run_triage(submission_id, record)

    # Audit trail
    audit = get_audit_service()
    await audit.log_change(
        "submission",
        submission_id,
        "triage",
        "ai-agent",
        changes={
            "status": result["status"],
            "risk_score": result["risk_score"],
            "recommendation": result["recommendation"],
        },
    )

    return TriageResult(
        submission_id=submission_id,
        status=SubmissionStatus(result["status"]),
        risk_score=result["risk_score"],
        recommendation=result["recommendation"],
        flags=result["flags"],
    )


@router.post(
    "/{submission_id}/quote",
    response_model=QuoteResponse,
    summary="Generate quote",
    description="Generate a premium quote using the Foundry underwriting agent "
    "and CyberRatingEngine. Includes authority check — if the premium "
    "exceeds the user's delegated authority, the submission is escalated.",
)
@limiter.limit("20/minute")
async def generate_quote(
    request: Request, submission_id: str, user: CurrentUser = Depends(get_current_user)
) -> QuoteResponse:
    """Generate a quote for the submission."""
    record = await _get_submission(submission_id)
    if record["status"] not in {SubmissionStatus.UNDERWRITING}:
        raise HTTPException(status_code=409, detail="Submission must be triaged before quoting")

    from openinsure.services.submission_service import SubmissionService

    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    svc = SubmissionService()
    result = await svc.generate_quote(submission_id, record, user_role, user.display_name)

    if result.get("escalated"):
        from starlette.responses import JSONResponse

        return JSONResponse(  # type: ignore[return-value]
            status_code=202,
            content={
                "status": "escalated",
                "escalation_id": result["escalation_id"],
                "reason": result["reason"],
                "required_role": result["required_role"],
                "message": f"Action requires approval from {result['required_role']}",
            },
        )

    # Audit trail
    audit = get_audit_service()
    await audit.log_change(
        "submission",
        submission_id,
        "update",
        user.display_name,
        changes={"status": "quoted", "premium": result["premium"]},
    )

    return QuoteResponse(
        submission_id=submission_id,
        quote_id=str(uuid.uuid4()),
        premium=result["premium"],
        currency="USD",
        coverages=result["coverages"],
        valid_until=result["valid_until"],
        authority=result.get("authority"),
        rating_breakdown=result.get("rating_breakdown"),
    )


@router.post("/{submission_id}/bind", response_model=BindResponse)
async def bind_submission(submission_id: str, user: CurrentUser = Depends(get_current_user)) -> BindResponse:
    """Bind the submission, creating a real policy and billing account."""
    record = await _get_submission(submission_id)
    if record["status"] != SubmissionStatus.QUOTED:
        raise HTTPException(status_code=409, detail="Submission must be quoted before binding")

    from openinsure.services.submission_service import SubmissionService

    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    svc = SubmissionService()
    result = await svc.bind(submission_id, record, user_role, user.display_name)

    if result.get("escalated"):
        from starlette.responses import JSONResponse

        return JSONResponse(  # type: ignore[return-value]
            status_code=202,
            content={
                "status": "escalated",
                "escalation_id": result["escalation_id"],
                "reason": result["reason"],
                "required_role": result["required_role"],
                "message": f"Action requires approval from {result['required_role']}",
            },
        )

    # Audit trail
    audit = get_audit_service()
    await audit.log_change(
        "submission",
        submission_id,
        "bind",
        user.display_name,
        changes={"policy_id": result["policy_id"], "premium": result.get("premium")},
    )
    await audit.log_change(
        "policy",
        result["policy_id"],
        "create",
        user.display_name,
        changes={
            "submission_id": submission_id,
            "policy_number": result.get("policy_number"),
            "premium": result.get("premium"),
        },
    )

    return BindResponse(
        submission_id=submission_id,
        policy_id=result["policy_id"],
        status=SubmissionStatus.BOUND,
        bound_at=result["bound_at"],
        authority=result.get("authority"),
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
            try:
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
            except Exception:
                _logger.warning("document.upload_to_blob_failed", doc_id=doc_id)

    record["updated_at"] = _now()
    return DocumentUploadResponse(submission_id=submission_id, document_ids=doc_ids)


class ReferRequest(BaseModel):
    """Request to refer a submission for senior review."""

    referral_reason: str = Field(..., min_length=1)


class ReferResponse(BaseModel):
    """Result of referring a submission."""

    submission_id: str
    status: SubmissionStatus
    referral_reason: str
    referred_at: str


@router.post("/{submission_id}/refer", response_model=ReferResponse)
async def refer_submission(submission_id: str, body: ReferRequest) -> ReferResponse:
    """Refer a submission for senior underwriter review."""
    record = await _get_submission(submission_id)
    if record["status"] != SubmissionStatus.UNDERWRITING:
        raise HTTPException(status_code=409, detail="Only submissions in underwriting can be referred")

    now = _now()
    record["status"] = SubmissionStatus.REFERRED
    record["referral_reason"] = body.referral_reason
    record["updated_at"] = now
    await _repo.update(
        submission_id,
        {"status": "referred", "referral_reason": body.referral_reason, "updated_at": now},
    )

    return ReferResponse(
        submission_id=submission_id,
        status=SubmissionStatus.REFERRED,
        referral_reason=body.referral_reason,
        referred_at=now,
    )


class DeclineRequest(BaseModel):
    """Request to decline a submission."""

    declination_reason: str = Field(..., min_length=1)


class DeclineResponse(BaseModel):
    """Result of declining a submission."""

    submission_id: str
    status: SubmissionStatus
    declination_reason: str
    declined_at: str


@router.post("/{submission_id}/decline", response_model=DeclineResponse)
async def decline_submission(submission_id: str, body: DeclineRequest) -> DeclineResponse:
    """Decline a submission with a required reason."""
    from openinsure.domain.state_machine import InvalidTransitionError, validate_submission_transition

    record = await _get_submission(submission_id)
    current_status = record["status"]
    try:
        validate_submission_transition(current_status, "declined")
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    now = _now()
    record["status"] = SubmissionStatus.DECLINED
    record["declination_reason"] = body.declination_reason
    record["updated_at"] = now
    await _repo.update(
        submission_id,
        {"status": "declined", "declination_reason": body.declination_reason, "updated_at": now},
    )

    return DeclineResponse(
        submission_id=submission_id,
        status=SubmissionStatus.DECLINED,
        declination_reason=body.declination_reason,
        declined_at=now,
    )


class SubjectivityRequest(BaseModel):
    """Add a subjectivity (condition to clear before binding)."""

    description: str = Field(..., min_length=1)
    due_date: str | None = Field(None, description="ISO-8601 date by which the subjectivity must be cleared")


class SubjectivityResponse(BaseModel):
    """Result of adding a subjectivity."""

    submission_id: str
    subjectivity_id: str
    description: str
    status: str
    due_date: str | None
    created_at: str


@router.post("/{submission_id}/subjectivities", response_model=SubjectivityResponse, status_code=201)
async def add_subjectivity(submission_id: str, body: SubjectivityRequest) -> SubjectivityResponse:
    """Add a subjectivity to a submission."""
    record = await _get_submission(submission_id)
    if record["status"] in {SubmissionStatus.BOUND, SubmissionStatus.DECLINED, SubmissionStatus.EXPIRED}:
        raise HTTPException(status_code=409, detail="Cannot add subjectivities to a terminal submission")

    sid = str(uuid.uuid4())
    now = _now()
    subjectivity = {
        "subjectivity_id": sid,
        "description": body.description,
        "status": "open",
        "due_date": body.due_date,
        "created_at": now,
    }

    if "subjectivities" not in record:
        record["subjectivities"] = []
    record["subjectivities"].append(subjectivity)
    record["updated_at"] = now
    await _repo.update(submission_id, {"subjectivities": record["subjectivities"], "updated_at": now})

    return SubjectivityResponse(
        submission_id=submission_id,
        subjectivity_id=sid,
        description=body.description,
        status="open",
        due_date=body.due_date,
        created_at=now,
    )


@router.post("/{submission_id}/enrich")
async def enrich_submission_endpoint(submission_id: str) -> dict[str, Any]:
    """Enrich a submission with external data sources."""
    record = await _repo.get_by_id(submission_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

    from openinsure.services.enrichment import enrich_submission

    enrichment_result = await enrich_submission(record)

    # Store enrichment data on the submission metadata
    metadata = record.get("metadata", record.get("extracted_data", {}))
    if isinstance(metadata, str):
        import json as _json

        try:
            metadata = _json.loads(metadata)
        except (ValueError, TypeError):
            metadata = {}
    metadata["enrichment_data"] = enrichment_result.get("enrichment_data", {})
    metadata["risk_summary"] = enrichment_result.get("risk_summary", {})

    await _repo.update(submission_id, {"metadata": metadata, "extracted_data": metadata})

    return {
        "submission_id": submission_id,
        "status": "enriched",
        **enrichment_result,
    }


@router.get("/{submission_id}/comparables")
async def get_submission_comparables(
    submission_id: str,
    limit: int = Query(5, ge=1, le=20, description="Max comparable accounts"),
) -> dict[str, Any]:
    """Find comparable accounts for a submission — similar past submissions
    by industry, revenue, security profile, and their outcomes (pricing,
    claims).  Addresses issue #87.
    """
    record = await _repo.get_by_id(submission_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

    from openinsure.services.comparable_accounts import get_comparable_finder

    finder = get_comparable_finder()
    comparables = await finder.find_comparables(record, limit=limit)
    return {
        "submission_id": submission_id,
        "comparables": comparables,
        "count": len(comparables),
    }


@router.post("/{submission_id}/process")
async def process_submission(submission_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, object]:
    """Run the full multi-agent new business workflow."""
    submission = await _repo.get_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    from openinsure.services.submission_service import SubmissionService

    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    svc = SubmissionService()
    return await svc.process(submission_id, submission, user_role, user.display_name)
