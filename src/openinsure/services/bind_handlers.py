"""Domain event handlers for cross-aggregate side-effects.

Each handler listens for a specific domain event and creates/updates
its own aggregate. Handlers are called synchronously for now —
async event-driven architecture is future work.

This module implements the DDD pattern where aggregates communicate
via domain events rather than directly modifying each other.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from openinsure.domain.events import DomainEvent

logger = structlog.get_logger()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PolicyCreationHandler:
    """Handles ``SubmissionBound`` → creates a Policy aggregate.

    Listens for the SubmissionBound event emitted by the Submission
    aggregate and creates the corresponding policy record.
    """

    async def handle(self, event: DomainEvent, context: dict[str, Any]) -> dict[str, Any] | None:
        """Create a policy from a SubmissionBound event.

        *context* must include:
        - ``policy_repo``: the policy repository
        - ``policy_data``: the fully-built policy dict
        - ``txn``: optional DB transaction

        Returns the created policy data dict, or None on failure.
        """
        if event.event_type != "submission.bound":
            return None

        policy_repo = context.get("policy_repo")
        policy_data = context.get("policy_data")
        txn = context.get("txn")

        if not policy_repo or not policy_data:
            logger.warning("policy_creation_handler.missing_context", event_id=str(event.event_id))
            return None

        try:
            if txn:
                await policy_repo.create(policy_data, txn=txn)
            else:
                await policy_repo.create(policy_data)

            # Denormalize coverages onto policy_coverages table (#317)
            try:
                from openinsure.infrastructure.factory import get_database_adapter

                db = get_database_adapter()
                if db:
                    for cov in policy_data.get("coverages", []):
                        if not isinstance(cov, dict):
                            continue
                        from uuid import uuid4

                        cov_id = str(uuid4())
                        params = [
                            cov_id,
                            policy_data.get("id"),
                            cov.get("coverage_code", ""),
                            cov.get("coverage_name", ""),
                            float(cov.get("limit", 0)),
                            float(cov.get("deductible", 0)),
                            float(cov.get("premium", 0)),
                        ]
                        if txn:
                            await db.execute_query(
                                """INSERT INTO policy_coverages
                                   (id, policy_id, coverage_code, coverage_name,
                                    coverage_limit, deductible, premium)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                params,
                                txn=txn,
                            )
                        else:
                            await db.execute_query(
                                """INSERT INTO policy_coverages
                                   (id, policy_id, coverage_code, coverage_name,
                                    coverage_limit, deductible, premium)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                params,
                            )
            except Exception:
                logger.warning(
                    "policy_creation_handler.coverage_denorm_failed",
                    policy_id=policy_data.get("id"),
                    exc_info=True,
                )

            logger.info(
                "policy_creation_handler.policy_created",
                policy_id=policy_data.get("id"),
                policy_number=policy_data.get("policy_number"),
                submission_id=str(event.aggregate_id),
            )
            return policy_data
        except Exception:
            logger.exception(
                "policy_creation_handler.failed",
                event_id=str(event.event_id),
                submission_id=str(event.aggregate_id),
            )
            raise


class BillingHandler:
    """Handles ``SubmissionBound`` → creates a billing account.

    Creates the billing account for the newly-bound policy.
    """

    async def handle(self, event: DomainEvent, context: dict[str, Any]) -> dict[str, Any] | None:
        """Create a billing account from a SubmissionBound event.

        *context* must include:
        - ``billing_create_fn``: async callable to create billing
        - ``policy_id``: the policy ID
        - ``policyholder_name``: the policyholder name
        - ``total_premium``: the premium amount
        - ``installments``: number of installments
        - ``effective_date``: policy effective date
        - ``txn``: optional DB transaction
        """
        if event.event_type != "submission.bound":
            return None

        billing_fn = context.get("billing_create_fn")
        if not billing_fn:
            logger.debug("billing_handler.no_billing_fn")
            return None

        try:
            kwargs: dict[str, Any] = {
                "policy_id": context["policy_id"],
                "policyholder_name": context.get("policyholder_name", "Unknown"),
                "total_premium": context.get("total_premium", 0),
                "installments": context.get("installments", 1),
                "effective_date": context.get("effective_date"),
            }
            txn = context.get("txn")
            if txn:
                kwargs["txn"] = txn
            billing_record = await billing_fn(**kwargs)

            # Link billing_account_id back to the policy (#318)
            billing_account_id = billing_record.get("id") if isinstance(billing_record, dict) else None
            if billing_account_id:
                policy_repo = context.get("policy_repo")
                if policy_repo:
                    try:
                        if txn:
                            await policy_repo.update(
                                context["policy_id"],
                                {"billing_account_id": billing_account_id},
                                txn=txn,
                            )
                        else:
                            await policy_repo.update(
                                context["policy_id"],
                                {"billing_account_id": billing_account_id},
                            )
                    except Exception:
                        logger.warning(
                            "billing_handler.link_billing_account_failed",
                            policy_id=context["policy_id"],
                            billing_account_id=billing_account_id,
                            exc_info=True,
                        )

            logger.info(
                "billing_handler.billing_created",
                policy_id=context["policy_id"],
                submission_id=str(event.aggregate_id),
            )
            return {"status": "created", "policy_id": context["policy_id"]}
        except Exception:
            logger.exception(
                "billing_handler.failed",
                event_id=str(event.event_id),
            )
            raise


class ReinsuranceHandler:
    """Handles ``SubmissionBound`` → creates reinsurance cessions.

    This is a best-effort operation — failure does not roll back the bind.
    """

    async def handle(self, event: DomainEvent, context: dict[str, Any]) -> dict[str, Any] | None:
        """Auto-calculate cessions from a SubmissionBound event.

        *context* must include:
        - ``cession_fn``: async callable ``(policy_id, policy_number, policy_data) -> None``
        - ``policy_id``: the policy ID
        - ``policy_number``: the policy number
        - ``policy_data``: the policy dict
        """
        if event.event_type != "submission.bound":
            return None

        cession_fn = context.get("cession_fn")
        if not cession_fn:
            logger.debug("reinsurance_handler.no_cession_fn")
            return None

        try:
            await cession_fn(
                context["policy_id"],
                context["policy_number"],
                context["policy_data"],
            )
            logger.info(
                "reinsurance_handler.cessions_created",
                policy_id=context["policy_id"],
            )
            return {"status": "created", "policy_id": context["policy_id"]}
        except Exception:
            # Cessions are non-critical — log but don't fail the bind
            logger.warning(
                "reinsurance_handler.failed",
                event_id=str(event.event_id),
                exc_info=True,
            )
            return None


async def dispatch_bind_events(
    events: list[DomainEvent],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch SubmissionBound events to all handlers synchronously.

    Called after the submission aggregate emits SubmissionBound. Runs
    handlers in order:
    1. PolicyCreationHandler (must succeed — in transaction)
    2. BillingHandler (must succeed — in transaction)
    3. ReinsuranceHandler (best-effort — outside transaction)

    Returns a summary dict with handler results.
    """
    results: dict[str, Any] = {}

    policy_handler = PolicyCreationHandler()
    billing_handler = BillingHandler()
    reinsurance_handler = ReinsuranceHandler()

    for event in events:
        if event.event_type != "submission.bound":
            continue

        # Critical handlers — failures should propagate
        results["policy"] = await policy_handler.handle(event, context)
        results["billing"] = await billing_handler.handle(event, context)

        # Non-critical handler — best effort
        results["reinsurance"] = await reinsurance_handler.handle(event, context)

    return results
