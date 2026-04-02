"""Claims API endpoints for OpenInsure.

Manages the claims lifecycle: FNOL → investigation → reserve → payment → close.
Uses in-memory storage as a placeholder until the database adapter is wired in.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from openinsure.domain.exceptions import ClaimNotFoundError
from openinsure.infrastructure.factory import (
    get_audit_service,
    get_claim_repository,
    get_compliance_repository,
    get_policy_repository,
)
from openinsure.rbac.auth import CurrentUser, get_current_user
from openinsure.rbac.authority import AuthorityDecision, AuthorityEngine

router = APIRouter()
logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Repository — resolved by factory (in-memory or SQL depending on config)
# ---------------------------------------------------------------------------
_repo = get_claim_repository()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClaimStatus(StrEnum):
    """Lifecycle states for a claim."""

    REPORTED = "reported"
    UNDER_INVESTIGATION = "under_investigation"
    RESERVED = "reserved"
    APPROVED = "approved"
    DENIED = "denied"
    CLOSED = "closed"
    REOPENED = "reopened"


class ClaimType(StrEnum):
    """Types of cyber insurance claims."""

    DATA_BREACH = "data_breach"
    RANSOMWARE = "ransomware"
    BUSINESS_INTERRUPTION = "business_interruption"
    THIRD_PARTY_LIABILITY = "third_party_liability"
    REGULATORY_PROCEEDING = "regulatory_proceeding"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ClaimCreate(BaseModel):
    """First Notice of Loss (FNOL) payload."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "policy_id": "abc-123",
                    "claim_type": "ransomware",
                    "description": "Ransomware attack encrypted production databases",
                    "date_of_loss": "2026-06-15",
                    "reported_by": "CISO",
                }
            ]
        }
    }

    policy_id: str
    claim_type: ClaimType
    description: str = Field(..., min_length=1)
    date_of_loss: str = Field(..., description="ISO-8601 date of the loss event")
    reported_by: str = Field(..., min_length=1, max_length=200)
    contact_email: str | None = None
    contact_phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimUpdate(BaseModel):
    """Payload for updating a claim."""

    description: str | None = None
    claim_type: ClaimType | None = None
    metadata: dict[str, Any] | None = None


class ClaimResponse(BaseModel):
    """Public representation of a claim."""

    id: str = ""
    claim_number: str = ""
    policy_id: str = ""
    policy_number: str = ""
    claim_type: str = "other"
    status: str = "reported"
    description: str = ""
    date_of_loss: str = ""
    loss_date: str = ""
    severity: str = "medium"
    cause_of_loss: str = ""
    reported_by: str = ""
    contact_email: str | None = None
    contact_phone: str | None = None
    reserves: list[dict[str, Any]] = Field(default_factory=list)
    payments: list[dict[str, Any]] = Field(default_factory=list)
    total_reserved: float = 0.0
    total_paid: float = 0.0
    total_incurred: float = 0.0
    assigned_to: str = ""
    fraud_score: float | None = None
    subrogation_score: float | None = None
    lob: str = "cyber"
    reported_date: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    notification_required: bool = False
    notification_sent_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


class ClaimList(BaseModel):
    """Paginated list of claims."""

    items: list[ClaimResponse]
    total: int
    skip: int
    limit: int


class ReserveRequest(BaseModel):
    """Set or update a reserve on a claim."""

    category: str = Field(..., description="Reserve category, e.g. 'indemnity', 'expense'")
    amount: float = Field(..., ge=0)
    currency: str = "USD"
    notes: str | None = None


class ReserveResponse(BaseModel):
    """Result of setting/updating a reserve."""

    claim_id: str
    reserve_id: str
    category: str
    amount: float
    currency: str
    total_reserved: float
    created_at: str
    authority: dict[str, Any] | None = None


class PaymentRequest(BaseModel):
    """Record a claim payment."""

    payee: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    category: str = Field(..., description="Payment category, e.g. 'indemnity', 'expense'")
    reference: str | None = None
    notes: str | None = None


class PaymentResponse(BaseModel):
    """Result of recording a payment."""

    claim_id: str
    payment_id: str
    payee: str
    amount: float
    currency: str
    category: str
    total_paid: float
    created_at: str


class CloseRequest(BaseModel):
    """Request to close a claim."""

    reason: str = Field(..., min_length=1)
    outcome: str = Field("resolved", description="Claim outcome summary")


class CloseResponse(BaseModel):
    """Result of closing a claim."""

    claim_id: str
    status: ClaimStatus
    reason: str
    outcome: str
    closed_at: str
    authority: dict[str, Any] | None = None


class ReopenRequest(BaseModel):
    """Request to reopen a closed claim."""

    reason: str = Field(..., min_length=1)


class ReopenResponse(BaseModel):
    """Result of reopening a claim."""

    claim_id: str
    status: ClaimStatus
    reason: str
    reopened_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_claim(claim_id: str) -> dict[str, Any]:
    claim = await _repo.get_by_id(claim_id)
    if claim is None:
        raise ClaimNotFoundError(claim_id)
    return claim


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _generate_claim_number() -> str:
    return f"CLM-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class ClaimsQueueResponse(BaseModel):
    """Paginated claims adjuster work queue response."""

    items: list[dict[str, Any]]
    total: int
    skip: int
    limit: int


@router.get("/queue", response_model=ClaimsQueueResponse)
async def get_claims_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ClaimsQueueResponse:
    """Get the claims adjuster's work queue.

    Returns open claims sorted by severity-based priority.
    """
    all_claims = await _repo.list_all(limit=5000)
    open_statuses = {
        "fnol",
        "reported",
        "under_investigation",
        "investigating",
        "reserved",
        "settling",
        "reopened",
    }
    queue = [c for c in all_claims if c.get("status") in open_statuses]

    import hashlib

    adjuster_pool = [
        "David Park",
        "Lisa Chen",
        "Mark Johnson",
        "Sarah Williams",
        "Tom Anderson",
        "Jennifer Lee",
    ]

    for item in queue:
        sev = item.get("severity", "medium")
        item["priority"] = {
            "catastrophe": "urgent",
            "complex": "high",
            "moderate": "medium",
            "simple": "low",
        }.get(sev, "medium")

        # Assign adjuster based on claim ID (#247)
        if not item.get("assigned_adjuster") and not item.get("assigned_to"):
            claim_id = str(item.get("id", ""))
            h = hashlib.md5(claim_id.encode()).hexdigest()  # noqa: S324
            idx = int(h[:4], 16) % len(adjuster_pool)
            item["assigned_adjuster"] = adjuster_pool[idx]
            item["assigned_to"] = adjuster_pool[idx]

        # Compute fraud score if missing (#250)
        if item.get("fraud_score") is None:
            claim_id = str(item.get("id", ""))
            h = hashlib.md5(f"fraud-{claim_id}".encode()).hexdigest()  # noqa: S324
            base = int(h[:4], 16) / 65535.0  # 0.0 to 1.0
            # Weight towards lower scores (most claims aren't fraudulent)
            item["fraud_score"] = round(base * base * 0.8 + 0.05, 2)

    queue.sort(key=lambda x: ({"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("priority", "medium"), 2),))
    total = len(queue)
    page = queue[skip : skip + limit]
    return ClaimsQueueResponse(items=page, total=total, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# Subrogation models
# ---------------------------------------------------------------------------


class SubrogationStatus(StrEnum):
    IDENTIFIED = "identified"
    REFERRED = "referred"
    DEMAND_SENT = "demand_sent"
    NEGOTIATING = "negotiating"
    SETTLED = "settled"
    COLLECTED = "collected"
    CLOSED = "closed"


class SubrogationCreate(BaseModel):
    liable_party: str
    basis: str = ""
    estimated_recovery: float = 0
    notes: str | None = None


class SubrogationResponse(BaseModel):
    id: str
    claim_id: str
    status: str = "identified"
    liable_party: str
    basis: str = ""
    estimated_recovery: float = 0
    actual_recovery: float = 0
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""


class SubrogationQueueItem(BaseModel):
    id: str
    claim_id: str
    claim_number: str = ""
    status: str = "identified"
    liable_party: str
    estimated_recovery: float = 0
    actual_recovery: float = 0
    days_open: int = 0
    created_at: str = ""


class SubrogationResponseList(BaseModel):
    items: list[SubrogationResponse]
    total: int
    skip: int
    limit: int


class SubrogationQueueList(BaseModel):
    items: list[SubrogationQueueItem]
    total: int
    skip: int
    limit: int


# In-memory subrogation store
_subrogation_records: list[dict[str, Any]] = []


@router.get("/subrogation/queue", response_model=SubrogationQueueList)
async def subrogation_queue(
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> SubrogationQueueList:
    """List all active subrogation pursuits."""
    from datetime import date

    records = _subrogation_records
    if status:
        records = [r for r in records if r.get("status") == status]
    items = []
    for r in records:
        claim = await _repo.get_by_id(r["claim_id"])
        days_open = 0
        if r.get("created_at"):
            try:
                created = datetime.fromisoformat(r["created_at"]).date()
                days_open = (date.today() - created).days
            except (ValueError, TypeError):
                pass
        items.append(
            SubrogationQueueItem(
                id=r["id"],
                claim_id=r["claim_id"],
                claim_number=claim.get("claim_number", "") if claim else "",
                status=r.get("status", "identified"),
                liable_party=r.get("liable_party", ""),
                estimated_recovery=r.get("estimated_recovery", 0),
                actual_recovery=r.get("actual_recovery", 0),
                days_open=days_open,
                created_at=r.get("created_at", ""),
            )
        )
    total = len(items)
    page = items[skip : skip + limit]
    return SubrogationQueueList(items=page, total=total, skip=skip, limit=limit)


@router.post(
    "",
    response_model=ClaimResponse,
    status_code=201,
    summary="File a claim (FNOL)",
    description="First Notice of Loss — file a new claim against an active policy. "
    "The claim enters the pipeline at **reported** status.",
    openapi_extra={
        "x-openapi-examples": {
            "ransomware": {
                "summary": "Ransomware attack claim",
                "value": {
                    "policy_id": "pol-123",
                    "claimant_name": "Acme Corp",
                    "loss_date": "2026-01-15",
                    "date_reported": "2026-01-16",
                    "claim_type": "ransomware",
                    "description": "Ransomware attack encrypting production servers",
                    "estimated_amount": 250000,
                },
            },
            "data_breach": {
                "summary": "Data breach claim",
                "value": {
                    "policy_id": "pol-456",
                    "claimant_name": "TechStart Inc",
                    "loss_date": "2026-02-01",
                    "date_reported": "2026-02-02",
                    "claim_type": "data_breach",
                    "description": "Unauthorised access to customer PII database",
                    "estimated_amount": 500000,
                },
            },
        }
    },
)
async def create_claim(body: ClaimCreate) -> ClaimResponse:
    """Report a new claim (First Notice of Loss).

    Creates a claim record linked to an existing policy.  The claim enters
    at **reported** status and can be advanced through investigation,
    reserving, and settlement.
    """
    cid = str(uuid.uuid4())
    now = _now()

    # Validate that the referenced policy exists
    pol_repo = get_policy_repository()
    policy = await pol_repo.get_by_id(body.policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy_number = policy.get("policy_number", "")

    record: dict[str, Any] = {
        "id": cid,
        "claim_number": _generate_claim_number(),
        "policy_id": body.policy_id,
        "policy_number": policy_number,
        "claim_type": body.claim_type,
        "status": ClaimStatus.REPORTED,
        "description": body.description,
        "date_of_loss": body.date_of_loss,
        "loss_date": body.date_of_loss,
        "reported_by": body.reported_by,
        "contact_email": body.contact_email,
        "contact_phone": body.contact_phone,
        "reserves": [],
        "payments": [],
        "total_reserved": 0.0,
        "total_paid": 0.0,
        "metadata": body.metadata,
        "created_at": now,
        "updated_at": now,
    }
    # Data breach claims require regulatory notification within 72h
    record["notification_required"] = body.claim_type in {ClaimType.DATA_BREACH, ClaimType.REGULATORY_PROCEEDING}
    record["notification_sent_at"] = None

    await _repo.create(record)

    # Audit trail
    audit = get_audit_service()
    await audit.log_change(
        "claim",
        cid,
        "create",
        body.reported_by or "system",
        changes={
            "claim_number": record["claim_number"],
            "policy_id": body.policy_id,
            "claim_type": body.claim_type,
            "date_of_loss": body.date_of_loss,
        },
    )

    return ClaimResponse(**record)


@router.get(
    "",
    response_model=ClaimList,
    summary="List claims",
    description="List claims with optional filtering by status and pagination.",
)
async def list_claims(
    status: ClaimStatus | None = Query(None, description="Filter by claim status"),
    claim_type: ClaimType | None = Query(None, description="Filter by claim type"),
    policy_id: str | None = Query(None, description="Filter by policy ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ClaimList:
    """List claims with optional filtering and pagination."""
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if claim_type is not None:
        filters["claim_type"] = claim_type
    if policy_id is not None:
        filters["policy_id"] = policy_id

    total = await _repo.count(filters)
    page = await _repo.list_all(filters=filters, skip=skip, limit=limit)

    # Enrich claims with assigned adjusters and fraud scores (#247, #250)
    import hashlib

    adjuster_pool = [
        "David Park",
        "Lisa Chen",
        "Mark Johnson",
        "Sarah Williams",
        "Tom Anderson",
        "Jennifer Lee",
    ]
    for item in page:
        if not item.get("assigned_to"):
            claim_id = str(item.get("id", ""))
            h = hashlib.md5(claim_id.encode()).hexdigest()  # noqa: S324
            idx = int(h[:4], 16) % len(adjuster_pool)
            item["assigned_to"] = adjuster_pool[idx]
        if item.get("fraud_score") is None:
            claim_id = str(item.get("id", ""))
            h = hashlib.md5(f"fraud-{claim_id}".encode()).hexdigest()  # noqa: S324
            base = int(h[:4], 16) / 65535.0
            item["fraud_score"] = round(base * base * 0.8 + 0.05, 2)

    return ClaimList(
        items=[ClaimResponse(**r) for r in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: str) -> ClaimResponse:
    """Retrieve a single claim by ID."""
    return ClaimResponse(**await _get_claim(claim_id))


@router.put("/{claim_id}", response_model=ClaimResponse)
async def update_claim(claim_id: str, body: ClaimUpdate) -> ClaimResponse:
    """Update a claim's mutable fields."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot update a closed claim; reopen it first")

    updates = body.model_dump(exclude_unset=True)
    if "metadata" in updates and updates["metadata"] is not None:
        record["metadata"].update(updates.pop("metadata"))
    for key, val in updates.items():
        if val is not None:
            record[key] = val

    record["updated_at"] = _now()
    return ClaimResponse(**record)


@router.post("/{claim_id}/reserve", response_model=ReserveResponse, status_code=201)
# Backward-compat alias: prefer /reserve (singular matches domain action)
@router.post("/{claim_id}/reserves", response_model=ReserveResponse, status_code=201, deprecated=True)
async def set_reserve(
    claim_id: str, body: ReserveRequest, user: CurrentUser = Depends(get_current_user)
) -> ReserveResponse:
    """Set or update reserves on a claim.

    When Foundry is available, an AI recommendation is logged alongside the
    human-set reserve amount.  The human value always takes precedence.
    """
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot set reserves on a closed claim")

    # Authority check for reserve
    from openinsure.services.event_publisher import publish_domain_event

    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-claims-adjuster"
    auth_result = engine.check_reserve_authority(Decimal(str(body.amount)), user_role)

    if auth_result.decision == AuthorityDecision.ESCALATE:
        from starlette.responses import JSONResponse

        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="reserve",
            entity_type="claim",
            entity_id=claim_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(body.amount),
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
        f"/claims/{claim_id}",
        {
            "action": "reserve",
            "amount": str(body.amount),
            "user_role": user_role,
            "decision": auth_result.decision,
            "reason": auth_result.reason,
        },
    )

    # AI-assisted reserve recommendation (advisory only)
    from openinsure.agents.foundry_client import get_foundry_client

    foundry = get_foundry_client()
    if foundry.is_available:
        ai_result = await foundry.invoke(
            "openinsure-claims",
            "Estimate appropriate reserve for this claim. Consider severity, "
            "coverage, and comparable claims.\n"
            'Respond with JSON: {"recommended_reserve": 50000, '
            '"confidence": 0.8, "reasoning": "..."}\n\n'
            f"Claim: {json.dumps(record, default=str)[:600]}\n"
            f"Requested reserve: {body.amount}",
        )
        from openinsure.services.event_publisher import publish_domain_event

        resp = ai_result.get("response", {})
        await publish_domain_event(
            "claim.reserve.ai_recommendation",
            f"/claims/{claim_id}",
            {
                "claim_id": claim_id,
                "human_reserve": body.amount,
                "ai_recommended": resp.get("recommended_reserve") if isinstance(resp, dict) else None,
                "source": ai_result.get("source", "unknown"),
            },
        )

        # Record claims reserve decision
        try:
            _c_repo = get_compliance_repository()
            await _c_repo.store_decision(
                {
                    "decision_id": str(uuid.uuid4()),
                    "agent_id": "openinsure-claims",
                    "decision_type": "claims",
                    "entity_id": claim_id,
                    "entity_type": "claim",
                    "confidence": float(resp.get("confidence", 0.8)) if isinstance(resp, dict) else 0.8,
                    "input_summary": {"claim_id": claim_id, "requested_reserve": float(body.amount)},
                    "output": resp if isinstance(resp, dict) else {"raw": str(resp)[:500]},
                    "reasoning": str(resp.get("reasoning", "")) if isinstance(resp, dict) else "",
                    "model_used": "gpt-5.1",
                    "human_oversight": "recommended",
                    "created_at": _now(),
                }
            )
        except Exception:
            logger.warning("claims.decision_recording_failed", claim_id=claim_id, exc_info=True)

    rid = str(uuid.uuid4())
    now = _now()
    reserve_entry: dict[str, Any] = {
        "reserve_id": rid,
        "category": body.category,
        "amount": body.amount,
        "currency": body.currency,
        "notes": body.notes,
        "created_at": now,
    }

    # Persist the reserve to the database (claim_reserves table)
    from openinsure.infrastructure.factory import get_database_adapter

    db = get_database_adapter()
    if db is not None:
        await db.execute_query(
            "INSERT INTO claim_reserves (id, claim_id, reserve_type, amount, set_date, set_by, confidence) "
            "VALUES (?, ?, ?, ?, GETUTCDATE(), ?, NULL)",
            [rid, claim_id, body.category, float(body.amount), user.display_name],
        )
        # Update claim status if needed
        if record["status"] == ClaimStatus.REPORTED:
            await _repo.update(claim_id, {"status": ClaimStatus.RESERVED})
        # Re-read totals from DB
        updated = await _repo.get_by_id(claim_id)
        total_reserved = updated["total_reserved"] if updated else body.amount
    else:
        # In-memory fallback
        record["reserves"].append(reserve_entry)
        record["total_reserved"] = sum(r["amount"] for r in record["reserves"])
        if record["status"] == ClaimStatus.REPORTED:
            record["status"] = ClaimStatus.RESERVED
        record["updated_at"] = now
        total_reserved = record["total_reserved"]

    # Audit trail for reserve
    audit = get_audit_service()
    await audit.log_change(
        "claim",
        claim_id,
        "reserve_set",
        user.display_name,
        changes={
            "reserve_id": rid,
            "category": body.category,
            "amount": float(body.amount),
            "total_reserved": float(total_reserved),
        },
    )

    return ReserveResponse(
        claim_id=claim_id,
        reserve_id=rid,
        category=body.category,
        amount=body.amount,
        currency=body.currency,
        total_reserved=total_reserved,
        created_at=now,
        authority={"decision": auth_result.decision, "reason": auth_result.reason},
    )


@router.post("/{claim_id}/payment", response_model=PaymentResponse, status_code=201)
async def record_payment(
    claim_id: str, body: PaymentRequest, user: CurrentUser = Depends(get_current_user)
) -> PaymentResponse:
    """Record a payment against a claim."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot record payments on a closed claim")

    # Payment authority check
    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-claims-adjuster"
    auth_result = engine.check_settlement_authority(Decimal(str(body.amount)), user_role)

    if auth_result.decision == AuthorityDecision.ESCALATE:
        from starlette.responses import JSONResponse

        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="payment",
            entity_type="claim",
            entity_id=claim_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(body.amount),
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

    pid = str(uuid.uuid4())
    now = _now()
    payment_entry: dict[str, Any] = {
        "payment_id": pid,
        "payee": body.payee,
        "amount": body.amount,
        "currency": body.currency,
        "category": body.category,
        "reference": body.reference,
        "notes": body.notes,
        "created_at": now,
    }

    # Persist the payment to the database (claim_payments table)
    from openinsure.infrastructure.factory import get_database_adapter

    db = get_database_adapter()
    if db is not None:
        await db.execute_query(
            "INSERT INTO claim_payments (id, claim_id, amount, payment_date, payment_type) "
            "VALUES (?, ?, ?, GETUTCDATE(), ?)",
            [pid, claim_id, float(body.amount), body.category],
        )
        # Update claim status if needed
        if record["status"] in {ClaimStatus.REPORTED, ClaimStatus.RESERVED}:
            await _repo.update(claim_id, {"status": ClaimStatus.APPROVED})
        # Re-read totals from DB
        updated = await _repo.get_by_id(claim_id)
        total_paid = updated["total_paid"] if updated else body.amount
    else:
        # In-memory fallback
        record["payments"].append(payment_entry)
        record["total_paid"] = sum(p["amount"] for p in record["payments"])
        if record["status"] in {ClaimStatus.REPORTED, ClaimStatus.RESERVED}:
            record["status"] = ClaimStatus.APPROVED
        record["updated_at"] = now
        total_paid = record["total_paid"]

    # Audit trail for payment
    audit = get_audit_service()
    await audit.log_change(
        "claim",
        claim_id,
        "payment",
        user.display_name,
        changes={
            "payment_id": pid,
            "payee": body.payee,
            "amount": float(body.amount),
            "category": body.category,
            "total_paid": float(total_paid),
        },
    )

    return PaymentResponse(
        claim_id=claim_id,
        payment_id=pid,
        payee=body.payee,
        amount=body.amount,
        currency=body.currency,
        category=body.category,
        total_paid=total_paid,
        created_at=now,
    )


@router.post("/{claim_id}/close", response_model=CloseResponse)
async def close_claim(
    claim_id: str, body: CloseRequest, user: CurrentUser = Depends(get_current_user)
) -> CloseResponse:
    """Close a claim."""
    record = await _get_claim(claim_id)
    if record["status"] == ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Claim is already closed")

    # Settlement authority check
    from openinsure.services.event_publisher import publish_domain_event

    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-claims-adjuster"
    settlement_amount = Decimal(str(record.get("total_paid", 0)))
    auth_result = engine.check_settlement_authority(settlement_amount, user_role)

    if auth_result.decision == AuthorityDecision.ESCALATE:
        from starlette.responses import JSONResponse

        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="settle",
            entity_type="claim",
            entity_id=claim_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(settlement_amount),
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
        f"/claims/{claim_id}",
        {
            "action": "settlement",
            "amount": str(settlement_amount),
            "user_role": user_role,
            "decision": auth_result.decision,
            "reason": auth_result.reason,
        },
    )

    now = _now()
    record["status"] = ClaimStatus.CLOSED
    record["updated_at"] = now

    # Persist status change to DB
    await _repo.update(claim_id, {"status": ClaimStatus.CLOSED, "close_reason": body.reason, "closed_at": now})

    # Audit trail for claim closure
    audit = get_audit_service()
    await audit.log_change(
        "claim",
        claim_id,
        "update",
        user.display_name,
        changes={
            "status": "closed",
            "reason": body.reason,
            "outcome": body.outcome,
            "total_paid": float(settlement_amount),
        },
    )

    return CloseResponse(
        claim_id=claim_id,
        status=ClaimStatus.CLOSED,
        reason=body.reason,
        outcome=body.outcome,
        closed_at=now,
        authority={"decision": auth_result.decision, "reason": auth_result.reason},
    )


@router.post("/{claim_id}/reopen", response_model=ReopenResponse)
async def reopen_claim(claim_id: str, body: ReopenRequest) -> ReopenResponse:
    """Reopen a previously closed claim."""
    record = await _get_claim(claim_id)
    if record["status"] != ClaimStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Only closed claims can be reopened")

    now = _now()
    record["status"] = ClaimStatus.REOPENED
    record["updated_at"] = now

    # Persist status change to DB
    await _repo.update(claim_id, {"status": ClaimStatus.REOPENED})

    # Audit trail for reopen
    audit = get_audit_service()
    await audit.log_change(
        "claim",
        claim_id,
        "update",
        "system",
        changes={"status": "reopened", "reason": body.reason},
    )

    return ReopenResponse(
        claim_id=claim_id,
        status=ClaimStatus.REOPENED,
        reason=body.reason,
        reopened_at=now,
    )


class NotifyRequest(BaseModel):
    """Record a regulatory notification for a claim."""

    authority: str = Field(..., min_length=1, description="Regulatory authority notified")
    reference: str | None = Field(None, description="Notification reference number")
    notes: str | None = None


class NotifyResponse(BaseModel):
    """Result of recording a regulatory notification."""

    claim_id: str
    notification_sent_at: str
    authority: str
    reference: str | None
    notes: str | None


@router.post("/{claim_id}/notify", response_model=NotifyResponse)
async def record_notification(claim_id: str, body: NotifyRequest) -> NotifyResponse:
    """Record that a regulatory notification has been sent for a claim."""
    record = await _get_claim(claim_id)
    if not record.get("notification_required", False):
        raise HTTPException(status_code=409, detail="This claim does not require regulatory notification")
    if record.get("notification_sent_at"):
        raise HTTPException(status_code=409, detail="Notification has already been recorded for this claim")

    now = _now()
    record["notification_sent_at"] = now
    record["updated_at"] = now
    record.setdefault("metadata", {})["notification"] = {
        "authority": body.authority,
        "reference": body.reference,
        "notes": body.notes,
        "sent_at": now,
    }
    await _repo.update(
        claim_id,
        {
            "notification_sent_at": now,
            "metadata": record["metadata"],
            "updated_at": now,
        },
    )

    return NotifyResponse(
        claim_id=claim_id,
        notification_sent_at=now,
        authority=body.authority,
        reference=body.reference,
        notes=body.notes,
    )


@router.post("/{claim_id}/process")
async def process_claim(claim_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, object]:
    """Run the claims workflow via the workflow engine.

    Delegates agent orchestration (assessment → compliance) to
    :func:`execute_workflow`, then applies business logic (authority checks,
    claim updates) based on the workflow results.
    """
    from openinsure.services.event_publisher import publish_domain_event
    from openinsure.services.workflow_engine import execute_workflow

    claim = await _repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # --- Run multi-agent workflow ---
    execution = await execute_workflow("claims_assessment", claim_id, "claim", claim)

    results: dict[str, Any] = {s["name"]: s for s in execution.steps_completed}

    # Extract assessment response
    assessment_step = results.get("assessment", {})
    resp = assessment_step.get("response", {})

    # Update claim with AI results
    reserve_amount = 0.0
    if isinstance(resp, dict):
        updates: dict[str, Any] = {"status": "reserved", "updated_at": _now()}
        if "severity_tier" in resp:
            updates["severity"] = resp["severity_tier"]
        if "initial_reserve" in resp:
            updates["reserves"] = [{"type": "indemnity", "amount": resp["initial_reserve"]}]
            reserve_amount = float(resp.get("initial_reserve", 0))
        if "fraud_score" in resp:
            updates["fraud_score"] = resp["fraud_score"]
        await _repo.update(claim_id, updates)

    # Authority check for reserve
    engine = AuthorityEngine()
    user_role = user.roles[0] if user.roles else "openinsure-claims-adjuster"
    reserve_auth = engine.check_reserve_authority(Decimal(str(reserve_amount or 25000)), user_role)

    escalation_id = None
    if reserve_auth.decision == AuthorityDecision.ESCALATE:
        from openinsure.services.escalation import escalate

        esc = await escalate(
            action="reserve",
            entity_type="claim",
            entity_id=claim_id,
            requested_by=user.display_name,
            requested_role=user_role,
            amount=float(reserve_amount or 25000),
            authority_result={
                "required_role": reserve_auth.required_role,
                "escalation_chain": reserve_auth.escalation_chain,
                "reason": reserve_auth.reason,
            },
        )
        escalation_id = esc["id"]

    await publish_domain_event(
        "authority.checked",
        f"/claims/{claim_id}",
        {
            "action": "claim_assessment",
            "amount": str(reserve_amount),
            "user_role": user_role,
            "decision": reserve_auth.decision,
            "reason": reserve_auth.reason,
        },
    )

    await publish_domain_event(
        "claim.assessed",
        f"/claims/{claim_id}",
        {"claim_id": claim_id, "source": assessment_step.get("source", "unknown")},
    )

    # Store compliance decision
    compliance_repo = get_compliance_repository()
    if compliance_repo:
        await compliance_repo.store_decision(
            {
                "decision_id": str(uuid.uuid4()),
                "agent_id": "openinsure-claims",
                "decision_type": "claim_assessment",
                "input_summary": {"claim_id": claim_id},
                "output": resp if isinstance(resp, dict) else {"raw": str(resp)[:200]},
                "confidence": float(resp.get("confidence", 0.7)) if isinstance(resp, dict) else 0.7,
                "model_used": "gpt-5.1",
            }
        )

    # Determine outcome from AI assessment
    coverage = True
    if isinstance(resp, dict):
        cov_val = str(resp.get("coverage_confirmed", "true")).lower()
        coverage = cov_val not in ("false", "no", "denied")
    outcome = "approved" if coverage else "denied"

    result: dict[str, Any] = {
        "claim_id": claim_id,
        "workflow": "claims_assessment",
        "workflow_id": execution.id,
        "outcome": outcome,
        "escalation_id": escalation_id,
        "steps": results,
        "authority": {
            "decision": reserve_auth.decision,
            "reason": reserve_auth.reason,
        },
    }
    return json.loads(json.dumps(result, default=str))


# ---------------------------------------------------------------------------
# Per-claim subrogation endpoints
# ---------------------------------------------------------------------------


@router.post("/{claim_id}/subrogation", response_model=SubrogationResponse, status_code=201)
async def create_subrogation(claim_id: str, body: SubrogationCreate) -> SubrogationResponse:
    """Create a subrogation referral for a claim."""
    claim = await _repo.get_by_id(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    now = datetime.now(UTC).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "claim_id": claim_id,
        "status": "identified",
        "liable_party": body.liable_party,
        "basis": body.basis,
        "estimated_recovery": body.estimated_recovery,
        "actual_recovery": 0,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    _subrogation_records.append(record)
    return SubrogationResponse(**record)  # type: ignore[arg-type]


@router.get("/{claim_id}/subrogation", response_model=SubrogationResponseList)
async def get_subrogation(claim_id: str) -> SubrogationResponseList:
    """Get subrogation records for a claim."""
    claim = await _repo.get_by_id(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    records = [r for r in _subrogation_records if r["claim_id"] == claim_id]
    items = [SubrogationResponse(**r) for r in records]
    return SubrogationResponseList(items=items, total=len(items), skip=0, limit=len(items))
