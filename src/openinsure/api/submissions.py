"""Submission API endpoints for OpenInsure.

Handles the full submission lifecycle: intake → triage → quote → bind.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import json
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
    risk_score: int = 0
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
    """Create a new insurance submission."""
    sid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": sid,
        "applicant_name": body.applicant_name,
        "applicant_email": body.applicant_email,
        "status": SubmissionStatus.RECEIVED,
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

    Calls the Foundry triage agent when available, falling back to
    deterministic local logic.
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
            premium = float(resp["recommended_premium"])
            record["status"] = SubmissionStatus.QUOTED
            record["quoted_premium"] = premium
            record["updated_at"] = _now()
            from openinsure.services.event_publisher import publish_domain_event

            # Authority check
            engine = AuthorityEngine()
            user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
            auth_result = engine.check_quote_authority(Decimal(str(premium)), user_role)
            if auth_result.decision == AuthorityDecision.ESCALATE:
                raise HTTPException(
                    403,
                    detail=f"Quote authority exceeded. {auth_result.reason}. "
                    f"Escalate to: {', '.join(auth_result.escalation_chain)}",
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
    valid_until = datetime(2099, 12, 31, tzinfo=UTC).isoformat()

    # Authority check
    from openinsure.services.event_publisher import publish_domain_event

    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-uw-analyst"
    auth_result = engine.check_quote_authority(Decimal(str(premium)), user_role)
    if auth_result.decision == AuthorityDecision.ESCALATE:
        raise HTTPException(
            403,
            detail=f"Quote authority exceeded. {auth_result.reason}. "
            f"Escalate to: {', '.join(auth_result.escalation_chain)}",
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
        raise HTTPException(
            403,
            detail=f"Bind authority exceeded. {auth_result.reason}. "
            f"Escalate to: {', '.join(auth_result.escalation_chain)}",
        )

    # Create the actual policy record
    policy_repo = get_policy_repository()
    policy_data = _build_policy_data(record, premium, policy_id=policy_id, policy_number=policy_number)
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
async def process_submission(submission_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, object]:
    """Run the full multi-agent new business workflow via Foundry agents.

    This is the real end-to-end pipeline:
    1. Triage (AI) → updates submission status
    2. Underwriting (AI) → sets quoted premium
    3. Policy bind → creates policy + billing records
    4. Compliance audit → logs decision records
    """
    from openinsure.agents.foundry_client import get_foundry_client
    from openinsure.infrastructure.factory import (
        get_billing_repository,
        get_compliance_repository,
        get_policy_repository,
    )
    from openinsure.services.event_publisher import publish_domain_event

    foundry = get_foundry_client()

    submission = await _repo.get_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    results: dict[str, Any] = {}
    now = _now()

    # Step 1: Triage
    triage = await foundry.invoke(
        "openinsure-submission",
        (
            "You are triaging a cyber insurance submission. Our appetite accepts:\n"
            "- IT/Tech companies (SIC 7xxx), Financial (SIC 6xxx), Professional Services\n"
            "- Revenue $500K to $50M\n"
            "- Security maturity score 4+ out of 10\n"
            "- Max 3 prior cyber incidents\n\n"
            "Respond ONLY with this exact JSON structure:\n"
            '{"appetite_match": "yes", "risk_score": 5, "priority": "medium", "confidence": 0.9, "reasoning": "..."}\n\n'
            f"Submission data:\n{json.dumps(submission, default=str)[:1000]}"
        ),
    )
    results["triage"] = triage

    # Update submission with triage results
    triage_resp = triage.get("response", {})
    appetite = "yes"  # default to yes
    if isinstance(triage_resp, dict):
        match_val = str(triage_resp.get("appetite_match", "yes")).lower().strip()
        appetite = "no" if match_val in ("no", "decline", "false", "reject", "outside") else "yes"
    elif isinstance(triage_resp, str):
        appetite = "no" if any(w in triage_resp.lower() for w in ["decline", "reject", "outside appetite"]) else "yes"
    await _repo.update(
        submission_id,
        {
            "status": "triaged",
            "triage_result": json.dumps(triage_resp) if isinstance(triage_resp, dict) else str(triage_resp),
            "updated_at": now,
        },
    )
    await publish_domain_event("submission.triaged", f"/submissions/{submission_id}", {"submission_id": submission_id})

    # Step 2: Underwriting & Pricing
    if appetite in ("no", "decline", "false"):
        await _repo.update(submission_id, {"status": "declined", "updated_at": now})
        await publish_domain_event(
            "submission.declined",
            f"/submissions/{submission_id}",
            {"submission_id": submission_id, "reason": "outside_appetite"},
        )
        return {
            "submission_id": submission_id,
            "workflow": "new_business",
            "outcome": "declined",
            "reason": "outside_appetite",
            "steps": results,
        }

    uw = await foundry.invoke(
        "openinsure-underwriting",
        (
            "You are pricing a cyber insurance submission. Calculate a premium.\n"
            "Base rate: $1.50 per $1000 revenue. Adjust for:\n"
            "- Industry risk (IT=1.0x, Healthcare=1.6x, Finance=1.5x)\n"
            "- Security maturity (8+=0.7x, 6+=0.85x, 4+=1.0x, <4=1.3x)\n"
            "- Prior incidents (0=1.0x, 1=1.25x, 2+=1.5x)\n\n"
            "Respond ONLY with this JSON:\n"
            '{"risk_score": 35, "recommended_premium": 12500, "confidence": 0.85, "key_factors": ["factor1", "factor2"]}\n\n'
            f"Submission:\n{json.dumps(submission, default=str)[:500]}\n"
            f"Triage: {json.dumps(triage_resp, default=str)[:300]}"
        ),
    )
    results["underwriting"] = uw

    # Extract premium from AI response
    uw_resp = uw.get("response", {})
    premium: float = 10000  # fallback
    if isinstance(uw_resp, dict):
        premium = float(uw_resp.get("recommended_premium", uw_resp.get("premium", 10000)) or 10000)
    await _repo.update(submission_id, {"status": "quoted", "quoted_premium": premium, "updated_at": now})
    await publish_domain_event(
        "submission.quoted", f"/submissions/{submission_id}", {"submission_id": submission_id, "premium": premium}
    )

    # Step 3: Auto-bind if premium within authority (uses AuthorityEngine)
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
    if bind_auth.decision != AuthorityDecision.ESCALATE:
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

    # Step 4: Compliance audit
    comp = await foundry.invoke(
        "openinsure-compliance",
        f"Audit this workflow for EU AI Act compliance.\nTriage={json.dumps(triage_resp, default=str)[:200]}\nUW={json.dumps(uw_resp, default=str)[:200]}",
    )
    results["compliance"] = comp

    # Store decision record
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
    return {
        "submission_id": submission_id,
        "workflow": "new_business",
        "outcome": outcome,
        "policy_id": policy_id,
        "policy_number": policy_number,
        "premium": premium,
        "steps": results,
        "authority": {
            "decision": bind_auth.decision,
            "reason": bind_auth.reason,
        },
    }
