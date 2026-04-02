"""Policy API endpoints for OpenInsure.

Manages the full policy lifecycle: issuance → endorsement → renewal → cancellation.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.domain.exceptions import PolicyNotFoundError
from openinsure.infrastructure.factory import get_audit_service, get_policy_repository

router = APIRouter()
_logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_policy_repository()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyStatus(StrEnum):
    """Lifecycle states for a policy."""

    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    RENEWED = "renewed"
    REINSTATED = "reinstated"
    SUSPENDED = "suspended"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    """Payload for creating a new policy."""

    submission_id: str
    product_id: str
    policyholder_name: str = Field(..., min_length=1, max_length=200)
    effective_date: str = Field(..., description="ISO-8601 date")
    expiration_date: str = Field(..., description="ISO-8601 date")
    premium: float = Field(..., gt=0)
    coverages: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyUpdate(BaseModel):
    """Payload for updating policy mutable fields."""

    policyholder_name: str | None = None
    metadata: dict[str, Any] | None = None


class PolicyResponse(BaseModel):
    """Public representation of a policy."""

    id: str = ""
    submission_id: str = ""
    product_id: str = ""
    policy_number: str = ""
    policyholder_name: str = ""
    insured_name: str = ""
    lob: str = "cyber"
    status: str = "active"
    effective_date: str = ""
    expiration_date: str = ""
    premium: float | None = None
    total_premium: float | None = None
    written_premium: float | None = None
    earned_premium: float | None = None
    unearned_premium: float | None = None
    coverages: list[dict[str, Any]] = Field(default_factory=list)
    endorsements: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    documents: list[str] = Field(default_factory=list)
    bound_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


class PolicyList(BaseModel):
    """Paginated list of policies."""

    items: list[PolicyResponse]
    total: int
    skip: int
    limit: int


class EndorsementRequest(BaseModel):
    """Request to create an endorsement on a policy."""

    description: str = Field(..., min_length=1)
    changes: dict[str, Any] = Field(default_factory=dict)
    effective_date: str = Field(..., description="ISO-8601 date")
    premium_delta: float = 0.0


class EndorsementResponse(BaseModel):
    """Result of an endorsement."""

    policy_id: str
    endorsement_id: str
    description: str
    changes: dict[str, Any]
    effective_date: str
    premium_delta: float
    created_at: str


class RenewalResponse(BaseModel):
    """Result of initiating a renewal."""

    policy_id: str
    renewal_policy_id: str
    status: PolicyStatus
    new_effective_date: str
    new_expiration_date: str


class CancelRequest(BaseModel):
    """Request to cancel a policy."""

    reason: str = Field(..., min_length=1)
    cancellation_date: str = Field(..., description="ISO-8601 effective cancellation date")
    method: str = Field("pro_rata", description="Cancellation method: pro_rata or short_rate")


class CancelResponse(BaseModel):
    """Result of cancelling a policy."""

    policy_id: str
    status: PolicyStatus
    reason: str
    cancellation_date: str
    cancelled_at: str
    return_premium: float = 0.0


class ReinstateRequest(BaseModel):
    """Request to reinstate a cancelled policy."""

    reason: str = Field(..., min_length=1)
    effective_date: str = Field(..., description="ISO-8601 reinstatement effective date")


class ReinstateResponse(BaseModel):
    """Result of reinstating a policy."""

    policy_id: str
    status: PolicyStatus
    reason: str
    reinstated_at: str


class DocumentItem(BaseModel):
    """A policy document reference."""

    document_id: str
    name: str
    type: str


class PolicyDocumentList(BaseModel):
    """List of documents attached to a policy."""

    policy_id: str
    documents: list[DocumentItem]


class PolicyTransactionResponse(BaseModel):
    """A single policy transaction record."""

    id: str
    policy_id: str
    transaction_type: str
    effective_date: str
    expiration_date: str | None = None
    premium_change: float = 0.0
    description: str | None = None
    coverages_snapshot: str | None = None
    terms_snapshot: str | None = None
    created_by: str | None = None
    created_at: str
    version: int = 1


class PolicyTransactionList(BaseModel):
    """List of transactions for a policy."""

    policy_id: str
    items: list[PolicyTransactionResponse]
    total: int
    skip: int = 0
    limit: int = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_policy(policy_id: str) -> dict[str, Any]:
    policy = await _repo.get_by_id(policy_id)
    if policy is None:
        raise PolicyNotFoundError(policy_id)
    return policy


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _generate_policy_number() -> str:
    return f"POL-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=201,
    summary="Create policy",
    description="Create a new policy record, typically as a result of binding a submission.",
)
async def create_policy(body: PolicyCreate) -> PolicyResponse:
    """Create a policy (typically from binding a submission)."""
    pid = str(uuid.uuid4())
    now = _now()
    record: dict[str, Any] = {
        "id": pid,
        "submission_id": body.submission_id,
        "product_id": body.product_id,
        "policy_number": _generate_policy_number(),
        "policyholder_name": body.policyholder_name,
        "insured_name": body.policyholder_name,
        "lob": "cyber",
        "status": PolicyStatus.ACTIVE,
        "effective_date": body.effective_date,
        "expiration_date": body.expiration_date,
        "premium": body.premium,
        "coverages": body.coverages,
        "endorsements": [],
        "metadata": body.metadata,
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(record)
    return PolicyResponse(**record)


@router.get(
    "",
    response_model=PolicyList,
    summary="List policies",
    description="List policies with optional filtering by status, policyholder, and product.",
)
async def list_policies(
    status: PolicyStatus | None = Query(None, description="Filter by policy status"),
    policyholder: str | None = Query(None, description="Filter by policyholder name (substring)"),
    product_id: str | None = Query(None, description="Filter by product ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PolicyList:
    """List policies with optional filtering and pagination."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if policyholder is not None:
        filters["policyholder_name__contains"] = policyholder
    if product_id is not None:
        filters["product_id"] = product_id

    total = await _repo.count(filters)
    page = await _repo.list_all(filters=filters, skip=skip, limit=limit)
    return PolicyList(
        items=[PolicyResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    as_of: str | None = Query(
        None,
        description="ISO-8601 datetime for temporal (time-travel) query, e.g. 2026-03-01T14:47:00",
    ),
) -> PolicyResponse:
    """Retrieve a single policy by ID.

    When ``as_of`` is provided, queries the policy state at that point in
    time using SQL Server temporal tables (``FOR SYSTEM_TIME AS OF``).
    Requires system-versioned temporal tables (migration 018).
    """
    if as_of:
        from openinsure.infrastructure.factory import get_database_adapter

        db = get_database_adapter()
        if db is None:
            # In-memory mode — temporal queries not supported, return current state
            return PolicyResponse(**await _get_policy(policy_id))

        from openinsure.infrastructure.repositories.sql_policies import (
            SqlPolicyRepository,
        )

        repo = SqlPolicyRepository(db)
        policy = await repo.get_by_id_as_of(policy_id, as_of)
        if policy is None:
            raise HTTPException(
                status_code=404,
                detail=f"Policy {policy_id} not found at {as_of}",
            )
        return PolicyResponse(**policy)
    return PolicyResponse(**await _get_policy(policy_id))


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(policy_id: str, body: PolicyUpdate) -> PolicyResponse:
    """Update a policy's mutable fields."""
    record = await _get_policy(policy_id)
    if record["status"] == PolicyStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Cannot update a cancelled policy")

    updates = body.model_dump(exclude_unset=True)
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    return PolicyResponse(**record)


@router.post("/{policy_id}/endorse", response_model=EndorsementResponse, status_code=201)
async def endorse_policy(policy_id: str, body: EndorsementRequest) -> EndorsementResponse:
    """Create an endorsement (mid-term change) on a policy."""
    record = await _get_policy(policy_id)
    if record["status"] != PolicyStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Endorsements require an active policy")

    eid = str(uuid.uuid4())
    now = _now()
    endorsement: dict[str, Any] = {
        "endorsement_id": eid,
        "description": body.description,
        "changes": body.changes,
        "effective_date": body.effective_date,
        "premium_delta": body.premium_delta,
        "created_at": now,
    }
    record["endorsements"].append(endorsement)
    record["premium"] += body.premium_delta
    record["updated_at"] = now

    # Apply coverage changes if specified
    if body.changes.get("add_coverage"):
        record.setdefault("coverages", []).append(body.changes["add_coverage"])
    if body.changes.get("remove_coverage"):
        code = body.changes["remove_coverage"]
        record["coverages"] = [c for c in record.get("coverages", []) if c.get("coverage_code") != code]
    if body.changes.get("update_limits"):
        for cov in record.get("coverages", []):
            if cov.get("coverage_code") == body.changes["update_limits"].get("coverage_code"):
                if "limit" in body.changes["update_limits"]:
                    cov["limit"] = body.changes["update_limits"]["limit"]
                if "deductible" in body.changes["update_limits"]:
                    cov["deductible"] = body.changes["update_limits"]["deductible"]

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "policy.endorsed",
            f"/policies/{policy_id}",
            {"policy_id": policy_id, "endorsement_id": eid, "premium_delta": body.premium_delta},
        )
    except Exception:
        _logger.debug("event.publish_skipped", event="policy.endorsed")

    # Audit trail
    audit = get_audit_service()
    await audit.log_change(
        "policy",
        policy_id,
        "endorse",
        "system",
        changes={"endorsement_id": eid, "description": body.description, "premium_delta": body.premium_delta},
    )

    return EndorsementResponse(policy_id=policy_id, **endorsement)


@router.post("/{policy_id}/renew", response_model=RenewalResponse, status_code=201)
async def renew_policy(policy_id: str) -> RenewalResponse:
    """Initiate a renewal for an active or expiring policy.

    Creates a new policy record with updated effective/expiration dates.
    """
    record = await _get_policy(policy_id)
    if record["status"] not in {PolicyStatus.ACTIVE, PolicyStatus.EXPIRED}:
        raise HTTPException(status_code=409, detail="Only active or expired policies can be renewed")

    # Mark original as renewed
    record["status"] = PolicyStatus.RENEWED
    record["updated_at"] = _now()

    # Create renewal policy
    new_pid = str(uuid.uuid4())
    now = _now()
    new_effective = record["expiration_date"]
    # Stub: add 1 year
    new_expiration = new_effective.replace(new_effective[:4], str(int(new_effective[:4]) + 1), 1)
    renewal: dict[str, Any] = {
        **record,
        "id": new_pid,
        "policy_number": _generate_policy_number(),
        "status": PolicyStatus.ACTIVE,
        "effective_date": new_effective,
        "expiration_date": new_expiration,
        "endorsements": [],
        "documents": [],
        "created_at": now,
        "updated_at": now,
    }
    await _repo.create(renewal)

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "policy.renewed",
            f"/policies/{policy_id}",
            {"policy_id": policy_id, "renewal_policy_id": new_pid},
        )
    except Exception:
        _logger.debug("event.publish_skipped", event="policy.renewed")

    return RenewalResponse(
        policy_id=policy_id,
        renewal_policy_id=new_pid,
        status=PolicyStatus.ACTIVE,
        new_effective_date=new_effective,
        new_expiration_date=new_expiration,
    )


@router.post("/{policy_id}/cancel", response_model=CancelResponse)
async def cancel_policy(policy_id: str, body: CancelRequest) -> CancelResponse:
    """Cancel an active policy with return premium calculation."""
    from openinsure.domain.state_machine import validate_policy_transition

    record = await _get_policy(policy_id)
    validate_policy_transition(record["status"], "cancelled")

    now = _now()

    # Calculate return premium (pro-rata or short-rate)
    total_premium = record.get("premium") or record.get("total_premium") or 0
    return_premium = 0.0
    if total_premium and record.get("effective_date") and record.get("expiration_date"):
        from datetime import date as date_type

        eff = date_type.fromisoformat(record["effective_date"][:10])
        exp = date_type.fromisoformat(record["expiration_date"][:10])
        cancel_dt = date_type.fromisoformat(body.cancellation_date[:10])
        total_days = (exp - eff).days or 1
        elapsed_days = max(0, (cancel_dt - eff).days)
        remaining_days = max(0, total_days - elapsed_days)

        if body.method == "short_rate":
            # Short-rate: carrier keeps a penalty (10% of return)
            pro_rata_return = total_premium * (remaining_days / total_days)
            return_premium = round(pro_rata_return * 0.9, 2)
        else:
            # Pro-rata: straight proportion
            return_premium = round(total_premium * (remaining_days / total_days), 2)

    record["status"] = PolicyStatus.CANCELLED
    record["updated_at"] = now

    try:
        from openinsure.services.event_publisher import publish_domain_event

        await publish_domain_event(
            "policy.cancelled",
            f"/policies/{policy_id}",
            {"policy_id": policy_id, "reason": body.reason, "return_premium": return_premium},
        )
    except Exception:
        _logger.debug("event.publish_skipped", event="policy.cancelled")

    return CancelResponse(
        policy_id=policy_id,
        status=PolicyStatus.CANCELLED,
        reason=body.reason,
        cancellation_date=body.cancellation_date,
        cancelled_at=now,
        return_premium=return_premium,
    )


@router.post("/{policy_id}/reinstate", response_model=ReinstateResponse)
async def reinstate_policy(policy_id: str, body: ReinstateRequest) -> ReinstateResponse:
    """Reinstate a cancelled policy."""
    from openinsure.domain.state_machine import validate_policy_transition

    record = await _get_policy(policy_id)
    validate_policy_transition(record["status"], "reinstated")

    now = _now()
    record["status"] = PolicyStatus.REINSTATED
    record["updated_at"] = now
    record.setdefault("metadata", {})["reinstatement"] = {
        "reason": body.reason,
        "effective_date": body.effective_date,
        "reinstated_at": now,
    }

    # Transition reinstated → active
    record["status"] = PolicyStatus.ACTIVE

    return ReinstateResponse(
        policy_id=policy_id,
        status=PolicyStatus.ACTIVE,
        reason=body.reason,
        reinstated_at=now,
    )


@router.get("/{policy_id}/transactions", response_model=PolicyTransactionList)
async def list_policy_transactions(policy_id: str) -> PolicyTransactionList:
    """List all transactions for a policy (time-travel history)."""
    from openinsure.services.policy_transaction_service import get_transactions

    await _get_policy(policy_id)  # Verify policy exists
    txns = await get_transactions(policy_id)
    return PolicyTransactionList(
        policy_id=policy_id,
        items=[PolicyTransactionResponse(**t) for t in txns],
        total=len(txns),
    )


@router.get("/{policy_id}/documents", response_model=PolicyDocumentList)
async def list_policy_documents(policy_id: str) -> PolicyDocumentList:
    """List documents attached to a policy.

    Stub — returns placeholder documents based on the IDs stored on the policy.
    """
    record = await _get_policy(policy_id)
    docs = [
        DocumentItem(document_id=did, name=f"document-{did[:8]}", type="application/pdf") for did in record["documents"]
    ]
    return PolicyDocumentList(policy_id=policy_id, documents=docs)


# ---------------------------------------------------------------------------
# Document generation endpoints (#78)
# ---------------------------------------------------------------------------


class GeneratedDocument(BaseModel):
    """Structured document content returned by the document generator."""

    title: str
    document_type: str
    policy_number: str
    sections: list[dict[str, Any]]
    effective_date: str
    summary: str
    generated_at: str


@router.get("/{policy_id}/documents/declaration", response_model=GeneratedDocument)
async def get_declaration_page(policy_id: str) -> GeneratedDocument:
    """Generate a declarations page for the policy."""
    policy = await _get_policy(policy_id)
    submission = policy.get("metadata", {})
    doc = await _generate_document_with_foundry(policy, submission, "declaration")
    return GeneratedDocument(**doc)


@router.get("/{policy_id}/documents/certificate", response_model=GeneratedDocument)
async def get_certificate(policy_id: str) -> GeneratedDocument:
    """Generate a Certificate of Insurance for the policy."""
    policy = await _get_policy(policy_id)
    submission = policy.get("metadata", {})
    doc = await _generate_document_with_foundry(policy, submission, "certificate")
    return GeneratedDocument(**doc)


@router.get("/{policy_id}/documents/schedule", response_model=GeneratedDocument)
async def get_coverage_schedule(policy_id: str) -> GeneratedDocument:
    """Generate a coverage schedule for the policy."""
    policy = await _get_policy(policy_id)
    submission = policy.get("metadata", {})
    doc = await _generate_document_with_foundry(policy, submission, "schedule")
    return GeneratedDocument(**doc)


async def _generate_document_with_foundry(
    policy: dict[str, Any],
    submission: dict[str, Any],
    doc_type: str,
) -> dict[str, Any]:
    """Try Foundry document agent, merge AI content; fall back to local generator."""
    from openinsure.agents.foundry_client import get_foundry_client
    from openinsure.agents.prompts import build_document_prompt
    from openinsure.services.document_generator import DocumentGenerator

    foundry = get_foundry_client()
    if foundry.is_available:
        try:
            prompt = build_document_prompt(policy, submission, doc_type)
            result = await foundry.invoke("openinsure-document", prompt)
            resp = result.get("response", {})
            if isinstance(resp, dict) and result.get("source") == "foundry":
                # Merge AI content into the base document structure
                base = DocumentGenerator().generate(policy, submission, doc_type)
                if resp.get("summary"):
                    base["summary"] = resp["summary"]
                if resp.get("sections"):
                    for ai_sec in resp["sections"]:
                        if not isinstance(ai_sec, dict):
                            continue
                        matched = next(
                            (s for s in base["sections"] if s["heading"] == ai_sec.get("heading")),
                            None,
                        )
                        if matched and ai_sec.get("content"):
                            matched["content"] = ai_sec["content"]
                        elif ai_sec.get("heading"):
                            base["sections"].append(ai_sec)
                base["source"] = "foundry"
                return base
        except Exception:
            import structlog

            structlog.get_logger().exception(
                "documents.foundry_generation_failed",
                policy_id=policy.get("id"),
                doc_type=doc_type,
            )

    # Deterministic fallback
    return DocumentGenerator().generate(policy, submission, doc_type)
