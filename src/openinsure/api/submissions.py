"""Submission API endpoints for OpenInsure.

Handles the full submission lifecycle: intake → triage → quote → bind.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_blob_storage, get_submission_repository

router = APIRouter()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_submission_repository()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubmissionStatus(StrEnum):
    """Lifecycle states for a submission."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_TRIAGE = "in_triage"
    TRIAGED = "triaged"
    QUOTING = "quoting"
    QUOTED = "quoted"
    BINDING = "binding"
    BOUND = "bound"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


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

    applicant_name: str = Field(..., min_length=1, max_length=200)
    applicant_email: str | None = None
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

    id: str
    applicant_name: str
    applicant_email: str | None = None
    status: SubmissionStatus
    channel: SubmissionChannel
    line_of_business: LineOfBusiness
    risk_data: dict[str, Any]
    metadata: dict[str, Any]
    documents: list[str]
    created_at: str
    updated_at: str


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


class BindResponse(BaseModel):
    """Result of binding a submission to a policy."""

    submission_id: str
    policy_id: str
    status: SubmissionStatus
    bound_at: str


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
    """Create a new insurance submission."""
    sid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": sid,
        "applicant_name": body.applicant_name,
        "applicant_email": body.applicant_email,
        "status": SubmissionStatus.SUBMITTED,
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
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    return SubmissionResponse(**record)


@router.post("/{submission_id}/triage", response_model=TriageResult)
async def triage_submission(submission_id: str) -> TriageResult:
    """Trigger AI triage on a submission.

    In the real implementation this dispatches to the triage agent; here
    we return a deterministic stub result.
    """
    record = await _get_submission(submission_id)
    if record["status"] not in {SubmissionStatus.SUBMITTED, SubmissionStatus.IN_TRIAGE}:
        raise HTTPException(status_code=409, detail="Submission is not in a triageable state")

    record["status"] = SubmissionStatus.TRIAGED
    record["updated_at"] = _now()

    return TriageResult(
        submission_id=submission_id,
        status=SubmissionStatus.TRIAGED,
        risk_score=0.42,
        recommendation="proceed_to_quote",
        flags=[],
    )


@router.post("/{submission_id}/quote", response_model=QuoteResponse)
async def generate_quote(submission_id: str) -> QuoteResponse:
    """Generate a quote for the submission.

    Stub implementation — the real version calls the rating engine.
    """
    record = await _get_submission(submission_id)
    if record["status"] not in {SubmissionStatus.TRIAGED, SubmissionStatus.QUOTING}:
        raise HTTPException(status_code=409, detail="Submission must be triaged before quoting")

    record["status"] = SubmissionStatus.QUOTED
    record["updated_at"] = _now()
    valid_until = datetime(2099, 12, 31, tzinfo=UTC).isoformat()

    return QuoteResponse(
        submission_id=submission_id,
        quote_id=str(uuid.uuid4()),
        premium=5000.00,
        currency="USD",
        coverages=[{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
        valid_until=valid_until,
    )


@router.post("/{submission_id}/bind", response_model=BindResponse)
async def bind_submission(submission_id: str) -> BindResponse:
    """Bind the submission, creating a policy.

    Stub implementation — the real version orchestrates policy issuance.
    """
    record = await _get_submission(submission_id)
    if record["status"] != SubmissionStatus.QUOTED:
        raise HTTPException(status_code=409, detail="Submission must be quoted before binding")

    record["status"] = SubmissionStatus.BOUND
    record["updated_at"] = _now()

    return BindResponse(
        submission_id=submission_id,
        policy_id=str(uuid.uuid4()),
        status=SubmissionStatus.BOUND,
        bound_at=_now(),
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

        content = await f.read()
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
async def process_submission(submission_id: str):
    """Trigger the full multi-agent new business workflow via Foundry agents."""
    from openinsure.agents.foundry_client import get_foundry_client

    foundry = get_foundry_client()

    submission = await _repo.get_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    results: dict[str, Any] = {}

    # Step 1: Triage
    triage = await foundry.invoke(
        "openinsure-submission",
        f"Triage this submission: {json.dumps(submission, default=str)[:1000]}",
    )
    results["triage"] = triage

    # Step 2: Underwriting (if appetite matched)
    uw = await foundry.invoke(
        "openinsure-underwriting",
        f"Assess and price: {json.dumps(submission, default=str)[:500]} "
        f"Triage: {json.dumps(triage.get('response', {}), default=str)[:300]}",
    )
    results["underwriting"] = uw

    # Step 3: Compliance
    comp = await foundry.invoke(
        "openinsure-compliance",
        f"Audit this workflow: Triage={json.dumps(triage.get('response', {}), default=str)[:200]} "
        f"UW={json.dumps(uw.get('response', {}), default=str)[:200]}",
    )
    results["compliance"] = comp

    return {"submission_id": submission_id, "workflow": "new_business", "steps": results}
