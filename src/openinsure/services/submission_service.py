"""Submission business logic service.

Encapsulates triage, quoting, binding, and full-workflow logic extracted
from API handlers.  API handlers delegate to this service to keep endpoint
code thin (~10 lines each).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import (
    get_billing_repository,
    get_policy_repository,
    get_submission_repository,
)
from openinsure.rbac.authority import AuthorityDecision, AuthorityEngine
from openinsure.services.rating import CyberRatingEngine, RatingInput

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Typed request/response models for critical service interfaces (#296)
# ---------------------------------------------------------------------------


class TriageInput(BaseModel):
    """Typed input for ``SubmissionService.run_triage``."""

    submission_id: str
    applicant: str = ""
    line_of_business: str = "cyber"
    annual_revenue: float = 0
    employee_count: int = 0
    industry: str = ""
    risk_data: dict[str, Any] = Field(default_factory=dict)
    cyber_risk_data: dict[str, Any] = Field(default_factory=dict)
    product_id: str | None = None
    status: str = ""

    @classmethod
    def from_record(cls, submission_id: str, record: dict[str, Any]) -> TriageInput:
        """Build from a raw submission dict."""
        return cls(
            submission_id=submission_id,
            applicant=record.get("applicant", ""),
            line_of_business=record.get("line_of_business", "cyber"),
            annual_revenue=_safe_float(record.get("annual_revenue", 0), 0),
            employee_count=int(record.get("employee_count", 0) or 0),
            industry=record.get("industry", ""),
            risk_data=_parse_json_field(record.get("risk_data", {})),
            cyber_risk_data=_parse_json_field(record.get("cyber_risk_data", {})),
            product_id=record.get("product_id"),
            status=record.get("status", ""),
        )


class TriageOutput(BaseModel):
    """Typed output from ``SubmissionService.run_triage``."""

    status: str
    risk_score: float
    recommendation: str
    flags: list[str] = Field(default_factory=list)


class QuoteInput(BaseModel):
    """Typed input for ``SubmissionService.generate_quote``."""

    submission_id: str
    user_role: str
    user_display_name: str

    @classmethod
    def from_args(
        cls,
        submission_id: str,
        user_role: str,
        user_display_name: str,
    ) -> QuoteInput:
        return cls(
            submission_id=submission_id,
            user_role=user_role,
            user_display_name=user_display_name,
        )


class QuoteOutput(BaseModel):
    """Typed output from ``SubmissionService.generate_quote``."""

    escalated: bool = False
    escalation_id: str | None = None
    reason: str | None = None
    required_role: str | None = None
    premium: float | None = None
    coverages: list[dict[str, Any]] | None = None
    valid_until: str | None = None
    authority: dict[str, str] | None = None
    rating_breakdown: dict[str, Any] | None = None


def _safe_float(value: Any, default: float, *, label: str = "value") -> float:
    """Safely coerce *value* to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        result = float(value)
        if result != result:  # NaN check
            logger.warning("submission_service.nan_value", label=label)
            return default
        return result
    except (TypeError, ValueError):
        logger.warning(
            "submission_service.bad_numeric_value",
            label=label,
            raw_value=str(value)[:200],
        )
        return default


# LOB-appropriate minimum premiums when all else fails
_LOB_MIN_PREMIUMS: dict[str, float] = {
    "cyber": 2500.0,
    "professional_indemnity": 1500.0,
    "directors_officers": 5000.0,
    "tech_eo": 2000.0,
}
_DEFAULT_MIN_PREMIUM = 2500.0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_json_field(raw: Any) -> dict[str, Any]:
    """Parse a field that may be a dict or a JSON string."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def _extract_risk_data(record: dict[str, Any]) -> dict[str, Any]:
    """Extract risk data from a submission record.

    Handles both ``risk_data`` and ``cyber_risk_data`` field names, and
    deserialises JSON strings when necessary.
    """
    raw = record.get("risk_data") or record.get("cyber_risk_data") or {}
    return _parse_json_field(raw)


def _build_rating_input(risk_data: dict[str, Any]) -> RatingInput:
    """Build a ``RatingInput`` from a risk-data dict.

    Applies safe defaults for any missing fields so the rating engine
    can always produce a result.
    """
    return RatingInput(
        annual_revenue=Decimal(str(risk_data.get("annual_revenue", 1_000_000))),
        employee_count=max(1, int(risk_data.get("employee_count", 10))),
        industry_sic_code=str(risk_data.get("industry_sic_code", "7372")),
        security_maturity_score=float(risk_data.get("security_maturity_score", 5.0)),
        has_mfa=bool(risk_data.get("has_mfa", False)),
        has_endpoint_protection=bool(risk_data.get("has_endpoint_protection", False)),
        has_backup_strategy=bool(risk_data.get("has_backup_strategy", False)),
        has_incident_response_plan=bool(risk_data.get("has_incident_response_plan", False)),
        prior_incidents=max(0, int(risk_data.get("prior_incidents", 0))),
        requested_limit=Decimal(str(risk_data.get("requested_limit", 1_000_000))),
        requested_deductible=Decimal(str(risk_data.get("requested_deductible", 10_000))),
    )


def _build_policy_data(
    submission: dict[str, Any],
    premium: float,
    *,
    policy_id: str | None = None,
    policy_number: str | None = None,
) -> dict[str, Any]:
    """Build a complete policy record from a submission."""
    now = _now()
    pid = policy_id or str(uuid.uuid4())
    pnum = policy_number or f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    applicant = submission.get("applicant_name", "") or submission.get("insured_name", "Unknown Insured")
    lob = submission.get("line_of_business", "cyber")

    cyber_data = _parse_json_field(submission.get("cyber_risk_data", {}))
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
        "effective_date": str(submission.get("requested_effective_date") or now[:10]),
        "expiration_date": str(
            submission.get("requested_expiration_date")
            or (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%d")
        ),
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


async def _record_decision(
    agent_id: str,
    decision_type: str,
    entity_id: str,
    entity_type: str,
    confidence: float,
    input_summary: dict[str, Any],
    output: dict[str, Any],
    reasoning: str,
) -> None:
    """Record a compliance decision (best-effort)."""
    try:
        from openinsure.infrastructure.factory import get_compliance_repository

        compliance_repo = get_compliance_repository()
        await compliance_repo.store_decision(
            {
                "decision_id": str(uuid.uuid4()),
                "agent_id": agent_id,
                "decision_type": decision_type,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "confidence": confidence,
                "input_summary": input_summary,
                "output": output,
                "reasoning": reasoning,
                "model_used": "gpt-5.1",
                "human_oversight": "required" if confidence < 0.7 else "recommended",
                "created_at": _now(),
            }
        )
    except Exception:
        logger.warning(
            "submission_service.decision_recording_failed",
            decision_type=decision_type,
            entity_id=entity_id,
            exc_info=True,
        )


async def _check_authority_and_escalate(
    action: str,
    premium: float,
    user_role: str,
    user_display_name: str,
    entity_id: str,
    limit: Decimal | None = None,
) -> dict[str, Any]:
    """Run authority check, escalating if needed.

    Returns a dict with ``escalated``, ``auth_result``, and optionally
    ``escalation_id``.
    """
    engine = AuthorityEngine()
    if action == "quote":
        auth_result = engine.check_quote_authority(Decimal(str(premium)), user_role)
    else:
        bind_limit = limit or Decimal("1000000")
        auth_result = engine.check_bind_authority(Decimal(str(premium)), user_role, bind_limit)

    if auth_result.decision == AuthorityDecision.ESCALATE:
        from openinsure.services.escalation import escalate

        esc = await escalate(
            action=action,
            entity_type="submission",
            entity_id=entity_id,
            requested_by=user_display_name,
            requested_role=user_role,
            amount=float(premium),
            authority_result={
                "required_role": auth_result.required_role,
                "escalation_chain": auth_result.escalation_chain,
                "reason": auth_result.reason,
            },
        )
        return {"escalated": True, "auth_result": auth_result, "escalation_id": esc["id"]}

    return {"escalated": False, "auth_result": auth_result}


async def _auto_cession(policy_id: str, policy_number: str, policy_data: dict[str, Any]) -> None:
    """Auto-calculate cessions based on active reinsurance treaties (best-effort).

    All cessions are created within a single transaction so partial
    cession sets are never committed.
    """
    try:
        from openinsure.domain.reinsurance import ReinsuranceContract
        from openinsure.infrastructure.factory import (
            get_cession_repository,
            get_database_adapter,
            get_reinsurance_repository,
        )
        from openinsure.services.reinsurance import calculate_cession

        treaty_repo = get_reinsurance_repository()
        cession_repo = get_cession_repository()
        raw_treaties = await treaty_repo.list_all(filters={"status": "active"})

        if not raw_treaties:
            return

        treaties = []
        for t in raw_treaties:
            try:
                treaties.append(
                    ReinsuranceContract(
                        id=t["id"],
                        treaty_number=t["treaty_number"],
                        treaty_type=t["treaty_type"],
                        reinsurer_name=t["reinsurer_name"],
                        status=t.get("status", "active"),
                        effective_date=t["effective_date"],
                        expiration_date=t["expiration_date"],
                        lines_of_business=t.get("lines_of_business", []),
                        retention=t.get("retention", 0),
                        limit=t.get("limit", 0),
                        rate=t.get("rate", 0),
                        capacity_total=t.get("capacity_total", 0),
                        capacity_used=t.get("capacity_used", 0),
                    )
                )
            except Exception:  # noqa: S112
                continue

        cessions = calculate_cession(policy_data, treaties)
        if not cessions:
            return

        db = get_database_adapter()
        if db:
            async with db.transaction() as cession_txn:
                for cession in cessions:
                    cession_record = {
                        "id": str(uuid.uuid4()),
                        "treaty_id": str(cession.treaty_id),
                        "policy_id": policy_id,
                        "policy_number": policy_number,
                        "ceded_premium": float(cession.ceded_premium),
                        "ceded_limit": float(cession.ceded_limit),
                        "cession_date": _now()[:10],
                        "created_at": _now(),
                    }
                    await cession_repo.create(cession_record, txn=cession_txn)

                    for raw_t in raw_treaties:
                        if str(raw_t.get("id")) == str(cession.treaty_id):
                            raw_t["capacity_used"] = raw_t.get("capacity_used", 0) + float(cession.ceded_limit)
                            break
        else:
            for cession in cessions:
                cession_record = {
                    "id": str(uuid.uuid4()),
                    "treaty_id": str(cession.treaty_id),
                    "policy_id": policy_id,
                    "policy_number": policy_number,
                    "ceded_premium": float(cession.ceded_premium),
                    "ceded_limit": float(cession.ceded_limit),
                    "cession_date": _now()[:10],
                    "created_at": _now(),
                }
                await cession_repo.create(cession_record)

                for raw_t in raw_treaties:
                    if str(raw_t.get("id")) == str(cession.treaty_id):
                        raw_t["capacity_used"] = raw_t.get("capacity_used", 0) + float(cession.ceded_limit)
                        break
    except Exception:
        logger.warning("submission_service.auto_cession_failed", exc_info=True)


class SubmissionService:
    """Service encapsulating all submission business logic.

    Each public method corresponds to a submission lifecycle action.
    API handlers delegate here; they should be thin (~10 LOC).
    """

    def __init__(self) -> None:
        self._repo = get_submission_repository()

    # ------------------------------------------------------------------
    # Triage
    # ------------------------------------------------------------------

    async def run_triage(self, submission_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Execute triage: assess risk appetite and advance to underwriting.

        Uses the Foundry triage agent when available (with prompt builder
        and compliance recording).  Falls back to rule-based local logic
        using the knowledge store.

        Returns a dict with keys: status, risk_score, recommendation, flags.
        """
        from openinsure.agents.foundry_client import get_foundry_client
        from openinsure.services.event_publisher import publish_domain_event

        foundry = get_foundry_client()

        if foundry.is_available:
            from openinsure.agents.prompts import build_triage_prompt, get_triage_context

            guidelines = await get_triage_context(record)
            triage_prompt = build_triage_prompt(record, guidelines=guidelines or None)
            result = await foundry.invoke("openinsure-submission", triage_prompt)
            resp = result.get("response", {})

            if isinstance(resp, dict) and result.get("source") == "foundry":
                now = _now()
                await self._repo.update(
                    submission_id,
                    {"status": "underwriting", "triage_result": json.dumps(resp), "updated_at": now},
                )

                await _record_decision(
                    agent_id="openinsure-submission",
                    decision_type="triage",
                    entity_id=submission_id,
                    entity_type="submission",
                    confidence=float(resp.get("confidence", 0.85)),
                    input_summary={"submission_id": submission_id, "prompt_length": len(triage_prompt)},
                    output=resp,
                    reasoning=str(resp.get("reasoning", "")),
                )

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

                return {
                    "status": "underwriting",
                    "risk_score": _safe_float(resp.get("risk_score", 5), default=5.0, label="risk_score"),
                    "recommendation": recommendation,
                    "flags": flags,
                }

        # Local fallback -- use knowledge store for rule-based triage
        from openinsure.infrastructure.knowledge_store import get_knowledge_store as get_mem_store

        mem = get_mem_store()
        lob = record.get("line_of_business", "cyber")
        gl = mem.get_guidelines(lob)
        risk_data = _parse_json_field(record.get("risk_data", {}))
        cyber_data = _parse_json_field(record.get("cyber_risk_data", {}))
        merged_risk = {**risk_data, **cyber_data}

        fallback_score = 5
        fallback_recommendation = "proceed_to_quote"
        fallback_flags: list[str] = ["source:local_fallback"]

        # -- Phase 3b (#164): check relational appetite rules first -------
        product_id = record.get("product_id")
        if product_id:
            try:
                from openinsure.infrastructure.factory import get_product_relations_repository

                relations = get_product_relations_repository()
                if relations is not None:
                    passes, reasons = await relations.check_appetite(product_id, merged_risk)
                    if not passes:
                        fallback_score = 8
                        fallback_flags.extend(reasons)
                        fallback_recommendation = "refer"
                        logger.info(
                            "triage.appetite_rules_failed",
                            product_id=product_id,
                            reasons=reasons,
                        )
            except Exception:
                logger.debug("triage.relational_appetite_check_failed", exc_info=True)

        if gl:
            appetite = gl.get("appetite", {})
            revenue = merged_risk.get("annual_revenue", 0) or 0
            rev_range = appetite.get("revenue_range", {})
            if revenue and (revenue < rev_range.get("min", 0) or revenue > rev_range.get("max", float("inf"))):
                fallback_score = 8
                fallback_flags.append("revenue_outside_appetite")
                fallback_recommendation = "refer"
            security_score = merged_risk.get("security_maturity_score", 0) or 0
            min_security = appetite.get("security_requirements", {}).get("minimum_score", 0)
            if security_score and security_score < min_security:
                fallback_score = max(fallback_score, 7)
                fallback_flags.append("security_below_minimum")
                fallback_recommendation = "refer"
            prior_incidents = merged_risk.get("prior_incidents", 0) or 0
            if prior_incidents > appetite.get("max_prior_incidents", 3):
                fallback_score = 9
                fallback_flags.append("incidents_exceed_maximum")
                fallback_recommendation = "decline"

        now = _now()
        fallback_triage = json.dumps(
            {
                "risk_score": fallback_score,
                "recommendation": fallback_recommendation,
                "source": "local_rule_based",
                "flags": fallback_flags,
            }
        )
        await self._repo.update(
            submission_id,
            {"status": "underwriting", "triage_result": fallback_triage, "updated_at": now},
        )

        return {
            "status": "underwriting",
            "risk_score": fallback_score,
            "recommendation": fallback_recommendation,
            "flags": fallback_flags,
        }

    # ------------------------------------------------------------------
    # Quote / Premium
    # ------------------------------------------------------------------

    async def generate_quote(
        self,
        submission_id: str,
        record: dict[str, Any],
        user_role: str,
        user_display_name: str,
    ) -> dict[str, Any]:
        """Generate a quote: Foundry underwriting, authority check, escalation.

        Returns a dict with either:
        - ``escalated=True`` plus escalation details, OR
        - quote details (premium, coverages, authority, rating_breakdown).
        """
        from openinsure.agents.foundry_client import get_foundry_client
        from openinsure.services.event_publisher import publish_domain_event

        foundry = get_foundry_client()

        if foundry.is_available:
            from openinsure.agents.prompts import (
                _get_rating_breakdown,
                build_underwriting_prompt,
                get_triage_context,
            )

            triage_result = _parse_json_field(record.get("triage_result", {})) or None
            guidelines = await get_triage_context(record)
            rating_breakdown = _get_rating_breakdown(record)
            underwriting_prompt = build_underwriting_prompt(
                record,
                triage_result=triage_result,
                guidelines=guidelines or None,
                rating_breakdown=rating_breakdown,
            )
            result = await foundry.invoke("openinsure-underwriting", underwriting_prompt)
            resp = result.get("response", {})

            if isinstance(resp, dict) and "recommended_premium" in resp:
                raw_premium = resp["recommended_premium"]
                premium = float(raw_premium) if raw_premium is not None else 5000.0
                premium = premium or 5000.0
                now = _now()

                from openinsure.infrastructure.factory import get_database_adapter as _get_db_quote

                _db_q = _get_db_quote()
                if _db_q:
                    async with _db_q.transaction() as _txn_q:
                        await self._repo.update(
                            submission_id,
                            {"status": "quoted", "quoted_premium": premium, "updated_at": now},
                            txn=_txn_q,
                        )
                else:
                    await self._repo.update(
                        submission_id,
                        {"status": "quoted", "quoted_premium": premium, "updated_at": now},
                    )

                await _record_decision(
                    agent_id="openinsure-underwriting",
                    decision_type="underwriting",
                    entity_id=submission_id,
                    entity_type="submission",
                    confidence=float(resp.get("confidence", 0.85)),
                    input_summary={"submission_id": submission_id, "prompt_length": len(underwriting_prompt)},
                    output=resp,
                    reasoning=str(resp.get("reasoning", "")),
                )

                # Authority check
                auth_info = await _check_authority_and_escalate(
                    "quote",
                    premium,
                    user_role,
                    user_display_name,
                    submission_id,
                )
                if auth_info["escalated"]:
                    return {
                        "escalated": True,
                        "escalation_id": auth_info["escalation_id"],
                        "reason": auth_info["auth_result"].reason,
                        "required_role": auth_info["auth_result"].required_role,
                    }

                auth_result = auth_info["auth_result"]
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

                return {
                    "escalated": False,
                    "premium": premium,
                    "coverages": [{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
                    "valid_until": now,
                    "authority": {"decision": auth_result.decision, "reason": auth_result.reason},
                    "rating_breakdown": rating_breakdown,
                }

        # Local fallback -- use deterministic rating engine (no hardcoded premium)
        premium = None
        rating_breakdown = None
        try:
            from openinsure.agents.prompts import _get_rating_breakdown

            rating_breakdown = _get_rating_breakdown(record)
            if rating_breakdown and rating_breakdown.get("final_premium"):
                premium = float(rating_breakdown["final_premium"])
                logger.info(
                    "submissions.fallback_quote_rated",
                    submission_id=submission_id,
                    premium=premium,
                    source="rating_engine",
                )
        except Exception:
            logger.debug("submissions.rating_engine_fallback_failed", exc_info=True)

        # Second attempt: CyberRatingEngine
        if premium is None:
            try:
                risk_data = _extract_risk_data(record)
                rating_input = _build_rating_input(risk_data)
                engine = CyberRatingEngine()
                rating_result = engine.calculate_premium(rating_input)
                premium = float(rating_result.final_premium)
                rating_breakdown = {
                    "final_premium": premium,
                    "confidence": rating_result.confidence,
                    "factors_applied": {k: float(v) for k, v in rating_result.factors_applied.items()},
                    "explanation": rating_result.explanation,
                }
                logger.info(
                    "submissions.fallback_quote_engine",
                    submission_id=submission_id,
                    premium=premium,
                    source="cyber_rating_engine",
                )
            except Exception:
                logger.warning("submissions.rating_engine_also_failed", submission_id=submission_id, exc_info=True)

        # Last resort: LOB-appropriate minimum premium
        if premium is None:
            lob = record.get("line_of_business", "cyber")
            premium = _LOB_MIN_PREMIUMS.get(lob, _DEFAULT_MIN_PREMIUM)
            logger.error("submissions.lob_minimum_fallback", submission_id=submission_id, premium=premium, lob=lob)

        now = _now()

        from openinsure.infrastructure.factory import get_database_adapter as _get_db_fb

        _db_fb = _get_db_fb()
        if _db_fb:
            async with _db_fb.transaction() as _txn_fb:
                await self._repo.update(
                    submission_id,
                    {"status": "quoted", "quoted_premium": premium, "updated_at": now},
                    txn=_txn_fb,
                )
        else:
            await self._repo.update(
                submission_id,
                {"status": "quoted", "quoted_premium": premium, "updated_at": now},
            )
        valid_until = datetime(2099, 12, 31, tzinfo=UTC).isoformat()

        # Authority check
        from openinsure.services.event_publisher import publish_domain_event

        auth_info = await _check_authority_and_escalate(
            "quote",
            premium,
            user_role,
            user_display_name,
            submission_id,
        )
        if auth_info["escalated"]:
            return {
                "escalated": True,
                "escalation_id": auth_info["escalation_id"],
                "reason": auth_info["auth_result"].reason,
                "required_role": auth_info["auth_result"].required_role,
            }

        auth_result = auth_info["auth_result"]
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

        return {
            "escalated": False,
            "premium": premium,
            "coverages": [{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
            "valid_until": valid_until,
            "authority": {"decision": auth_result.decision, "reason": auth_result.reason},
            "rating_breakdown": rating_breakdown,
        }

    # Keep backward-compatible alias used by other callers
    async def calculate_premium(self, submission_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Calculate premium (simple path without authority check).

        Tries Foundry first, falls back to the local CyberRatingEngine,
        and only uses a LOB-appropriate minimum premium as a last resort.
        """
        from openinsure.agents.foundry_client import get_foundry_client

        foundry = get_foundry_client()
        risk_data = _extract_risk_data(record)
        lob = record.get("line_of_business", record.get("lob", "cyber"))

        # --- Attempt 1: Foundry agent ---
        if foundry.is_available:
            try:
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
                    premium_val = _safe_float(raw_premium, default=0.0, label="recommended_premium")
                    if premium_val > 0:
                        logger.info(
                            "premium.foundry_calculated",
                            submission_id=submission_id,
                            premium=premium_val,
                        )
                        await self._repo.update(
                            submission_id,
                            {"status": "quoted", "quoted_premium": premium_val, "updated_at": _now()},
                        )
                        return {
                            "premium": premium_val,
                            "ai_mode": "foundry",
                            "coverages": [{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
                        }
            except Exception:
                logger.warning("premium.foundry_call_failed", submission_id=submission_id, exc_info=True)

        # --- Attempt 2: Local CyberRatingEngine ---
        try:
            rating_input = _build_rating_input(risk_data)
            engine = CyberRatingEngine()
            rating_result = engine.calculate_premium(rating_input)
            premium = float(rating_result.final_premium)

            logger.info(
                "premium.local_rating_engine",
                submission_id=submission_id,
                premium=premium,
                confidence=rating_result.confidence,
                factors=len(rating_result.factors_applied),
            )
            await self._repo.update(
                submission_id,
                {"status": "quoted", "quoted_premium": premium, "updated_at": _now()},
            )
            return {
                "premium": premium,
                "ai_mode": "local_rating_engine",
                "confidence": rating_result.confidence,
                "factors_applied": {k: float(v) for k, v in rating_result.factors_applied.items()},
                "explanation": rating_result.explanation,
                "warnings": rating_result.warnings,
                "coverages": [
                    {
                        "name": "Cyber Liability",
                        "limit": float(rating_input.requested_limit),
                        "deductible": float(rating_input.requested_deductible),
                    }
                ],
            }
        except Exception:
            logger.warning("premium.rating_engine_failed", submission_id=submission_id, exc_info=True)

        # --- Attempt 3: LOB-appropriate minimum premium ---
        premium = _LOB_MIN_PREMIUMS.get(lob, _DEFAULT_MIN_PREMIUM)
        logger.warning("premium.lob_minimum_fallback", submission_id=submission_id, premium=premium, lob=lob)
        await self._repo.update(
            submission_id,
            {"status": "quoted", "quoted_premium": premium, "updated_at": _now()},
        )
        return {
            "premium": premium,
            "ai_mode": "lob_minimum_fallback",
            "coverages": [{"name": "Cyber Liability", "limit": 1_000_000, "deductible": 10_000}],
        }

    # ------------------------------------------------------------------
    # Bind
    # ------------------------------------------------------------------

    async def bind(
        self,
        submission_id: str,
        record: dict[str, Any],
        user_role: str,
        user_display_name: str,
    ) -> dict[str, Any]:
        """Bind a submission: authority check, policy creation, billing, cessions, events.

        Uses the Submission aggregate root to validate the transition and
        emit a ``SubmissionBound`` event.  Downstream handlers
        (``PolicyCreationHandler``, ``BillingHandler``,
        ``ReinsuranceHandler``) each operate on their own aggregate
        boundary, following DDD aggregate separation.

        Returns a dict with either:
        - ``escalated=True`` plus escalation details, OR
        - bind details (policy_id, policy_number, premium, authority, bound_at).
        """
        from openinsure.agents.foundry_client import get_foundry_client
        from openinsure.domain.aggregates.submission import SubmissionAggregate
        from openinsure.services.bind_handlers import dispatch_bind_events
        from openinsure.services.event_publisher import publish_domain_event

        now = _now()
        policy_id = str(uuid.uuid4())
        policy_number = f"POL-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        premium = record.get("quoted_premium", 0) or record.get("total_premium", 10000)

        # Authority check
        cyber_data = _parse_json_field(record.get("risk_data", {}))
        limit = Decimal(str(cyber_data.get("requested_limit", 1000000) if cyber_data else 1000000))
        auth_info = await _check_authority_and_escalate(
            "bind",
            premium,
            user_role,
            user_display_name,
            submission_id,
            limit=limit,
        )
        if auth_info["escalated"]:
            return {
                "escalated": True,
                "escalation_id": auth_info["escalation_id"],
                "reason": auth_info["auth_result"].reason,
                "required_role": auth_info["auth_result"].required_role,
            }
        auth_result = auth_info["auth_result"]

        # ── Aggregate root: validate transition and emit SubmissionBound ──
        aggregate = SubmissionAggregate(record)
        aggregate.bind(policy_id=policy_id, policy_number=policy_number, premium=premium)

        # Build policy data
        policy_repo = get_policy_repository()
        policy_data = _build_policy_data(record, premium, policy_id=policy_id, policy_number=policy_number)

        # Invoke Foundry policy agent for issuance review (non-critical — outside txn)
        foundry = get_foundry_client()
        if foundry.is_available:
            from openinsure.agents.prompts import build_policy_review_prompt

            uw_result = _parse_json_field(record.get("triage_result", {})) or None
            policy_review_prompt = build_policy_review_prompt(record, underwriting_result=uw_result)
            policy_review = await foundry.invoke("openinsure-policy", policy_review_prompt)

            await publish_domain_event(
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

            pr_resp = policy_review.get("response", {})
            pr_confidence = float(pr_resp.get("confidence", 0.9)) if isinstance(pr_resp, dict) else 0.9
            await _record_decision(
                agent_id="openinsure-policy",
                decision_type="policy_review",
                entity_id=submission_id,
                entity_type="submission",
                confidence=pr_confidence,
                input_summary={
                    "submission_id": submission_id,
                    "policy_number": policy_number,
                    "prompt_length": len(policy_review_prompt),
                },
                output=pr_resp if isinstance(pr_resp, dict) else {"raw": str(pr_resp)[:500]},
                reasoning=str(pr_resp.get("notes", "")) if isinstance(pr_resp, dict) else "",
            )

        # ── Dispatch aggregate events via handlers ─────────────────────
        # PolicyCreationHandler + BillingHandler run inside the core
        # transaction.  ReinsuranceHandler is best-effort outside it.
        from openinsure.api.billing import create_billing_account_on_bind
        from openinsure.infrastructure.factory import get_database_adapter

        billing_plan = record.get("billing_plan", "full_pay")
        installments = {"full_pay": 1, "quarterly": 4, "monthly": 12}.get(billing_plan, 1)
        applicant = record.get("applicant_name", "") or record.get("insured_name", "Unknown")

        bind_events = aggregate.clear_events()

        db = get_database_adapter()
        if db:
            async with db.transaction() as txn:
                handler_ctx = {
                    "policy_repo": policy_repo,
                    "policy_data": policy_data,
                    "billing_create_fn": create_billing_account_on_bind,
                    "policy_id": policy_id,
                    "policyholder_name": applicant,
                    "total_premium": premium,
                    "installments": installments,
                    "effective_date": policy_data.get("effective_date"),
                    "txn": txn,
                }
                await dispatch_bind_events(bind_events, handler_ctx)
                await self._repo.update(submission_id, {"status": "bound", "updated_at": now}, txn=txn)
        else:
            handler_ctx = {
                "policy_repo": policy_repo,
                "policy_data": policy_data,
                "billing_create_fn": create_billing_account_on_bind,
                "policy_id": policy_id,
                "policyholder_name": applicant,
                "total_premium": premium,
                "installments": installments,
                "effective_date": policy_data.get("effective_date"),
            }
            await dispatch_bind_events(bind_events, handler_ctx)
            await self._repo.update(submission_id, {"status": "bound", "updated_at": now})

        # Auto-generate declaration page via Foundry document agent (non-critical)
        if foundry.is_available:
            try:
                from openinsure.agents.prompts import build_document_prompt

                doc_prompt = build_document_prompt(policy_data, record, "declaration")
                doc_result = await foundry.invoke("openinsure-document", doc_prompt)
                await publish_domain_event(
                    "policy.document_generated",
                    f"/policies/{policy_id}",
                    {
                        "policy_id": policy_id,
                        "document_type": "declaration",
                        "source": doc_result.get("source", "unknown"),
                    },
                )
                logger.info(
                    "submissions.bind_document_generated",
                    policy_id=policy_id,
                    source=doc_result.get("source", "unknown"),
                )
            except Exception:
                logger.warning("submissions.bind_document_generation_failed", policy_id=policy_id, exc_info=True)

        # Auto-calculate cessions via ReinsuranceHandler (best-effort, already
        # dispatched above when using handlers; call _auto_cession as fallback
        # for the non-handler code path in process())
        await _auto_cession(policy_id, policy_number, policy_data)

        # Publish domain events (non-critical — outside transaction)
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

        return {
            "escalated": False,
            "policy_id": policy_id,
            "policy_number": policy_number,
            "premium": premium,
            "authority": {"decision": auth_result.decision, "reason": auth_result.reason},
            "bound_at": now,
        }

    # Keep backward-compatible alias
    async def bind_policy(self, submission_id: str, record: dict[str, Any], user_role: str) -> dict[str, Any]:
        """Backward-compatible bind (without escalation via JSONResponse)."""
        return await self.bind(submission_id, record, user_role, user_display_name="system")

    # ------------------------------------------------------------------
    # Process (full workflow)
    # ------------------------------------------------------------------

    async def process(
        self,
        submission_id: str,
        submission: dict[str, Any],
        user_role: str,
        user_display_name: str,
    ) -> dict[str, Any]:
        """Run the full multi-agent new business workflow.

        Orchestrates: workflow engine -> triage interpretation -> premium
        extraction -> authority check -> auto-bind -> compliance recording.
        """
        from openinsure.infrastructure.factory import get_compliance_repository
        from openinsure.services.event_publisher import publish_domain_event
        from openinsure.services.workflow_engine import execute_workflow

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
            appetite = (
                "no" if any(w in triage_resp.lower() for w in ["decline", "reject", "outside appetite"]) else "yes"
            )

        await self._repo.update(
            submission_id,
            {
                "status": "underwriting",
                "triage_result": json.dumps(triage_resp) if isinstance(triage_resp, dict) else str(triage_resp),
                "updated_at": now,
            },
        )
        await publish_domain_event(
            "submission.triaged", f"/submissions/{submission_id}", {"submission_id": submission_id}
        )

        # Early decline if outside appetite
        if appetite in ("no", "decline", "false"):
            await self._repo.update(submission_id, {"status": "declined", "updated_at": now})
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
        premium: float = 10000
        if isinstance(uw_resp, dict):
            premium = float(uw_resp.get("recommended_premium", uw_resp.get("premium", 10000)) or 10000)
        await self._repo.update(
            submission_id,
            {
                "status": "quoted",
                "quoted_premium": premium,
                "triage_result": json.dumps(triage_resp) if isinstance(triage_resp, dict) else str(triage_resp),
                "updated_at": now,
            },
        )
        await publish_domain_event(
            "submission.quoted",
            f"/submissions/{submission_id}",
            {"submission_id": submission_id, "premium": premium},
        )

        # --- Authority check & auto-bind ---
        cyber_data = _parse_json_field(submission.get("cyber_risk_data", submission.get("risk_data", {})))
        bind_limit = Decimal(str(cyber_data.get("requested_limit", 1000000) if cyber_data else 1000000))

        auth_info = await _check_authority_and_escalate(
            "bind",
            premium,
            user_role,
            user_display_name,
            submission_id,
            limit=bind_limit,
        )
        bind_auth = auth_info["auth_result"]

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
        escalation_id = auth_info.get("escalation_id")

        if not auth_info["escalated"]:
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

            await _auto_cession(policy_id, policy_number, policy_data)

            await self._repo.update(submission_id, {"status": "bound", "updated_at": now})
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
                    "output": {
                        "premium": premium,
                        "policy_id": policy_id,
                        "outcome": "bound" if policy_id else "quoted",
                    },
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
