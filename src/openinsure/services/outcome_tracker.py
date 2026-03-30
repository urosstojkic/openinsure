"""Decision outcome tracking service.

Records real-world outcomes for AI decisions so the platform can measure
whether triage, underwriting, and claims decisions were accurate. This is
the core feedback loop that makes OpenInsure an AI-native platform — no
legacy system tracks whether its AI was *right*.

Outcome types:
- ``claim_filed``: A claim was filed against a policy whose submission was
  triaged/underwritten by an agent.
- ``renewal_retained``: A policy renewed, confirming the original
  underwriting decision was acceptable to the insured.
- ``premium_adequate``: Enough premium was collected relative to losses.
- ``fraud_confirmed``: A fraud flag raised by the claims agent was correct.
- ``reserve_sufficient``: The initial reserve estimate was adequate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from openinsure.infrastructure.factory import get_database_adapter

if TYPE_CHECKING:
    from decimal import Decimal

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Core recording
# ---------------------------------------------------------------------------


async def record_outcome(
    decision_id: str,
    outcome_type: str,
    *,
    outcome_value: Decimal | float | None = None,
    accuracy_score: float | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Persist a decision outcome to the ``decision_outcomes`` table.

    Returns the created record dict, or ``None`` when SQL is unavailable.
    """
    db = get_database_adapter()
    outcome_id = str(uuid4())
    now = datetime.now(UTC)

    if db is not None:
        try:
            await db.execute_query(
                """
                INSERT INTO decision_outcomes
                    (id, decision_id, outcome_type, outcome_value, accuracy_score,
                     measured_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    outcome_id,
                    decision_id,
                    outcome_type,
                    float(outcome_value) if outcome_value is not None else None,
                    accuracy_score,
                    now,
                    notes,
                ],
            )
            logger.info(
                "outcome.recorded",
                decision_id=decision_id,
                outcome_type=outcome_type,
                accuracy_score=accuracy_score,
            )
        except Exception as exc:
            logger.warning("outcome.record_failed", decision_id=decision_id, error=str(exc)[:200])
            return None
    else:
        # In-memory fallback — store in module-level list for tests
        _in_memory_outcomes.append(
            {
                "id": outcome_id,
                "decision_id": decision_id,
                "outcome_type": outcome_type,
                "outcome_value": float(outcome_value) if outcome_value is not None else None,
                "accuracy_score": accuracy_score,
                "measured_at": now.isoformat(),
                "notes": notes,
            }
        )
        logger.info(
            "outcome.recorded_in_memory",
            decision_id=decision_id,
            outcome_type=outcome_type,
        )

    return {
        "id": outcome_id,
        "decision_id": decision_id,
        "outcome_type": outcome_type,
        "outcome_value": float(outcome_value) if outcome_value is not None else None,
        "accuracy_score": accuracy_score,
        "measured_at": now.isoformat(),
        "notes": notes,
    }


# In-memory store for non-SQL mode
_in_memory_outcomes: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Claim-filed outcome wiring
# ---------------------------------------------------------------------------


async def record_claim_filed_outcome(
    policy_id: str,
    claim_id: str,
    loss_amount: Decimal | float | None = None,
) -> list[dict[str, Any]]:
    """When a claim is filed, find the original triage/underwriting decisions
    for the policy's submission and record ``claim_filed`` outcomes.

    Returns the list of outcome records created.
    """
    db = get_database_adapter()
    outcomes: list[dict[str, Any]] = []

    if db is None:
        # In-memory: no decision_records to look up
        logger.debug("outcome.claim_filed_skipped", reason="no_database")
        return outcomes

    try:
        # Find decisions related to this policy via the submission entity chain.
        # decision_records stores entity_id → we look for triage/underwriting
        # decisions whose entity_id matches the policy's submission_id (or the policy id itself).
        decisions = await db.fetch_all(
            """
            SELECT dr.id AS decision_id, dr.decision_type, dr.confidence
            FROM decision_records dr
            WHERE (
                dr.decision_type IN ('triage', 'underwriting', 'pricing', 'intake')
            )
            AND (
                -- Match by policy_id in output_data JSON
                dr.output_data LIKE ?
                -- Or entity_id referencing this policy
                OR EXISTS (
                    SELECT 1 FROM policies p
                    WHERE p.id = ? AND (
                        CAST(dr.id AS NVARCHAR(36)) IN (
                            SELECT value FROM STRING_SPLIT(
                                COALESCE(p.submission_id, ''), ','
                            )
                        )
                        OR dr.input_summary LIKE '%' + CAST(p.submission_id AS NVARCHAR(36)) + '%'
                    )
                )
            )
            ORDER BY dr.created_at ASC
            """,
            [f"%{policy_id}%", policy_id],
        )

        for dec in decisions:
            result = await record_outcome(
                decision_id=str(dec["decision_id"]),
                outcome_type="claim_filed",
                outcome_value=loss_amount,
                accuracy_score=_compute_claim_accuracy(dec.get("confidence")),
                notes=json.dumps(
                    {"claim_id": claim_id, "policy_id": policy_id, "loss_amount": str(loss_amount)},
                    default=str,
                ),
            )
            if result:
                outcomes.append(result)

    except Exception as exc:
        logger.warning("outcome.claim_filed_failed", policy_id=policy_id, error=str(exc)[:200])

    return outcomes


def _compute_claim_accuracy(original_confidence: float | None) -> float:
    """Compute a simple accuracy score for a triage decision when a claim is filed.

    A high-confidence "approve" that later has a claim suggests the risk
    assessment may have been too optimistic. Returns a value between 0 and 1.
    """
    if original_confidence is None:
        return 0.5
    # If confidence was high (agent was sure the risk was good) but a claim
    # was filed, accuracy is lower. If confidence was low (agent flagged
    # risk) and a claim was filed, the agent was right to flag it.
    return max(0.0, min(1.0, 1.0 - original_confidence))


# ---------------------------------------------------------------------------
# Renewal outcome wiring
# ---------------------------------------------------------------------------


async def record_renewal_outcome(policy_id: str) -> list[dict[str, Any]]:
    """When a policy renews, record ``renewal_retained`` for original decisions."""
    db = get_database_adapter()
    outcomes: list[dict[str, Any]] = []

    if db is None:
        logger.debug("outcome.renewal_skipped", reason="no_database")
        return outcomes

    try:
        decisions = await db.fetch_all(
            """
            SELECT dr.id AS decision_id, dr.decision_type, dr.confidence
            FROM decision_records dr
            WHERE dr.decision_type IN ('triage', 'underwriting', 'pricing')
            AND (
                dr.output_data LIKE ?
                OR dr.input_summary LIKE ?
            )
            ORDER BY dr.created_at ASC
            """,
            [f"%{policy_id}%", f"%{policy_id}%"],
        )

        for dec in decisions:
            result = await record_outcome(
                decision_id=str(dec["decision_id"]),
                outcome_type="renewal_retained",
                accuracy_score=min(1.0, (dec.get("confidence") or 0.5) + 0.1),
                notes=json.dumps({"policy_id": policy_id}, default=str),
            )
            if result:
                outcomes.append(result)

    except Exception as exc:
        logger.warning("outcome.renewal_failed", policy_id=policy_id, error=str(exc)[:200])

    return outcomes


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


async def get_outcomes_for_decision(decision_id: str) -> list[dict[str, Any]]:
    """Return all outcomes recorded against a given decision."""
    db = get_database_adapter()
    if db is not None:
        rows = await db.fetch_all(
            "SELECT * FROM decision_outcomes WHERE decision_id = ? ORDER BY measured_at ASC",
            [decision_id],
        )
        return [
            {
                "id": str(row["id"]),
                "decision_id": str(row["decision_id"]),
                "outcome_type": row["outcome_type"],
                "outcome_value": (float(row["outcome_value"]) if row.get("outcome_value") is not None else None),
                "accuracy_score": row.get("accuracy_score"),
                "measured_at": (
                    row["measured_at"].isoformat()
                    if hasattr(row["measured_at"], "isoformat")
                    else str(row["measured_at"])
                ),
                "notes": row.get("notes"),
            }
            for row in rows
        ]

    # In-memory fallback
    return [o for o in _in_memory_outcomes if o["decision_id"] == decision_id]


async def get_accuracy_report() -> dict[str, Any]:
    """Aggregate accuracy statistics by agent and outcome type.

    Returns a report with per-agent accuracy, per-outcome-type counts,
    and overall platform accuracy.
    """
    db = get_database_adapter()

    if db is not None:
        try:
            by_agent = await db.fetch_all(
                """
                SELECT
                    dr.agent_id,
                    do.outcome_type,
                    COUNT(*) AS outcome_count,
                    AVG(do.accuracy_score) AS avg_accuracy,
                    MIN(do.accuracy_score) AS min_accuracy,
                    MAX(do.accuracy_score) AS max_accuracy
                FROM decision_outcomes do
                JOIN decision_records dr ON do.decision_id = dr.id
                GROUP BY dr.agent_id, do.outcome_type
                ORDER BY dr.agent_id, do.outcome_type
                """
            )

            overall = await db.fetch_one(
                """
                SELECT
                    COUNT(*) AS total_outcomes,
                    AVG(accuracy_score) AS avg_accuracy,
                    COUNT(DISTINCT decision_id) AS decisions_measured
                FROM decision_outcomes
                """
            )

            avg_acc = round(overall["avg_accuracy"], 4) if overall and overall["avg_accuracy"] is not None else None

            return {
                "generated_at": datetime.now(UTC).isoformat(),
                "overall": {
                    "total_outcomes": overall["total_outcomes"] if overall else 0,
                    "avg_accuracy": avg_acc,
                    "decisions_measured": (overall["decisions_measured"] if overall else 0),
                },
                "by_agent": [
                    {
                        "agent_id": row["agent_id"],
                        "outcome_type": row["outcome_type"],
                        "outcome_count": row["outcome_count"],
                        "avg_accuracy": (round(row["avg_accuracy"], 4) if row["avg_accuracy"] is not None else None),
                        "min_accuracy": (round(row["min_accuracy"], 4) if row["min_accuracy"] is not None else None),
                        "max_accuracy": (round(row["max_accuracy"], 4) if row["max_accuracy"] is not None else None),
                    }
                    for row in by_agent
                ],
            }
        except Exception as exc:
            logger.warning("outcome.accuracy_report_failed", error=str(exc)[:200])

    # In-memory fallback
    from collections import defaultdict

    by_type: dict[str, list[float]] = defaultdict(list)
    for o in _in_memory_outcomes:
        if o.get("accuracy_score") is not None:
            by_type[o["outcome_type"]].append(o["accuracy_score"])

    total = len(_in_memory_outcomes)
    all_scores = [o["accuracy_score"] for o in _in_memory_outcomes if o.get("accuracy_score") is not None]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "overall": {
            "total_outcomes": total,
            "avg_accuracy": round(sum(all_scores) / len(all_scores), 4) if all_scores else None,
            "decisions_measured": len({o["decision_id"] for o in _in_memory_outcomes}),
        },
        "by_agent": [
            {
                "agent_id": "unknown",
                "outcome_type": otype,
                "outcome_count": len(scores),
                "avg_accuracy": round(sum(scores) / len(scores), 4) if scores else None,
                "min_accuracy": round(min(scores), 4) if scores else None,
                "max_accuracy": round(max(scores), 4) if scores else None,
            }
            for otype, scores in by_type.items()
        ],
    }
