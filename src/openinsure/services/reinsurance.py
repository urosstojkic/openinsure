"""Reinsurance business logic service.

Carrier-only module — handles cession calculations, recovery calculations,
and bordereau generation for reinsurance treaties.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog

from openinsure.domain.reinsurance import (
    CessionRecord,
    RecoveryRecord,
    ReinsuranceContract,
    TreatyStatus,
    TreatyType,
)

logger = structlog.get_logger()


def calculate_cession(
    policy: dict[str, Any],
    treaties: list[ReinsuranceContract],
) -> list[CessionRecord]:
    """Match a policy to applicable treaties and calculate ceded amounts.

    For each active treaty whose lines_of_business overlap with the policy's
    LOB, calculate the ceded premium and limit based on treaty type.
    """
    cessions: list[CessionRecord] = []
    policy_premium = Decimal(str(policy.get("premium", 0)))
    policy_limit = Decimal(str(policy.get("limit", policy_premium)))
    policy_lob = policy.get("lob", "")

    for treaty in treaties:
        if treaty.status != TreatyStatus.ACTIVE:
            continue

        # Check LOB applicability
        if treaty.lines_of_business and policy_lob not in treaty.lines_of_business:
            continue

        ceded_premium = Decimal("0")
        ceded_limit = Decimal("0")

        if treaty.treaty_type == TreatyType.QUOTA_SHARE:
            # Cede a fixed percentage of premium and limit
            cession_rate = treaty.rate / Decimal("100") if treaty.rate > 1 else treaty.rate
            ceded_premium = (policy_premium * cession_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ceded_limit = (policy_limit * cession_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        elif treaty.treaty_type == TreatyType.EXCESS_OF_LOSS:
            # Cede the portion above retention, up to treaty limit
            excess = policy_limit - treaty.retention
            if excess > 0:
                ceded_limit = min(excess, treaty.limit)
                ceded_premium = (
                    (policy_premium * (ceded_limit / policy_limit)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if policy_limit > 0
                    else Decimal("0")
                )

        elif treaty.treaty_type == TreatyType.SURPLUS:
            # Cede lines above retention
            excess = policy_limit - treaty.retention
            if excess > 0:
                ceded_limit = min(excess, treaty.limit)
                ceded_premium = (
                    (policy_premium * (ceded_limit / policy_limit)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if policy_limit > 0
                    else Decimal("0")
                )

        elif treaty.treaty_type == TreatyType.FACULTATIVE:
            # Facultative: cede at the treaty rate
            cession_rate = treaty.rate / Decimal("100") if treaty.rate > 1 else treaty.rate
            ceded_premium = (policy_premium * cession_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ceded_limit = (policy_limit * cession_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if ceded_premium > 0:
            cession = CessionRecord(
                treaty_id=treaty.id,
                policy_id=policy.get("id", ""),
                policy_number=policy.get("policy_number", ""),
                ceded_premium=ceded_premium,
                ceded_limit=ceded_limit,
                cession_date=date.today(),
            )
            cessions.append(cession)

            logger.info(
                "reinsurance.cession_calculated",
                treaty=treaty.treaty_number,
                policy=policy.get("policy_number"),
                ceded_premium=str(ceded_premium),
            )

    return cessions


def calculate_recovery(
    claim: dict[str, Any],
    treaties: list[ReinsuranceContract],
) -> list[RecoveryRecord]:
    """Calculate reinsurance recovery for a paid claim.

    Matches the claim against active treaties and calculates recoverable
    amounts based on treaty type and retention.
    """
    recoveries: list[RecoveryRecord] = []
    claim_amount = Decimal(str(claim.get("paid_amount", claim.get("reserve_amount", 0))))
    claim_lob = claim.get("lob", "")

    for treaty in treaties:
        if treaty.status != TreatyStatus.ACTIVE:
            continue

        if treaty.lines_of_business and claim_lob not in treaty.lines_of_business:
            continue

        recovery_amount = Decimal("0")

        if treaty.treaty_type == TreatyType.QUOTA_SHARE:
            cession_rate = treaty.rate / Decimal("100") if treaty.rate > 1 else treaty.rate
            recovery_amount = (claim_amount * cession_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        elif treaty.treaty_type in (TreatyType.EXCESS_OF_LOSS, TreatyType.SURPLUS):
            excess = claim_amount - treaty.retention
            if excess > 0:
                recovery_amount = min(excess, treaty.limit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        elif treaty.treaty_type == TreatyType.FACULTATIVE:
            cession_rate = treaty.rate / Decimal("100") if treaty.rate > 1 else treaty.rate
            recovery_amount = (claim_amount * cession_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if recovery_amount > 0:
            recovery = RecoveryRecord(
                treaty_id=treaty.id,
                claim_id=claim.get("id", ""),
                claim_number=claim.get("claim_number", ""),
                recovery_amount=recovery_amount,
                recovery_date=date.today(),
                status="pending",
            )
            recoveries.append(recovery)

            logger.info(
                "reinsurance.recovery_calculated",
                treaty=treaty.treaty_number,
                claim=claim.get("claim_number"),
                recovery_amount=str(recovery_amount),
            )

    return recoveries


def generate_bordereau(
    treaty: ReinsuranceContract,
    cessions: list[dict[str, Any]],
    recoveries: list[dict[str, Any]],
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, Any]:
    """Generate premium/claims bordereau for a treaty.

    Returns a summary report of all cessions and recoveries for the
    specified treaty and period.
    """
    # Filter cessions for this treaty
    treaty_cessions = [c for c in cessions if str(c.get("treaty_id")) == str(treaty.id)]
    treaty_recoveries = [r for r in recoveries if str(r.get("treaty_id")) == str(treaty.id)]

    # Apply period filter if provided
    if period_start:
        treaty_cessions = [
            c for c in treaty_cessions if c.get("cession_date") and c["cession_date"] >= str(period_start)
        ]
        treaty_recoveries = [
            r for r in treaty_recoveries if r.get("recovery_date") and r["recovery_date"] >= str(period_start)
        ]
    if period_end:
        treaty_cessions = [c for c in treaty_cessions if c.get("cession_date") and c["cession_date"] <= str(period_end)]
        treaty_recoveries = [
            r for r in treaty_recoveries if r.get("recovery_date") and r["recovery_date"] <= str(period_end)
        ]

    total_ceded_premium = sum(Decimal(str(c.get("ceded_premium", 0))) for c in treaty_cessions)
    total_ceded_limit = sum(Decimal(str(c.get("ceded_limit", 0))) for c in treaty_cessions)
    total_recoveries = sum(Decimal(str(r.get("recovery_amount", 0))) for r in treaty_recoveries)

    bordereau = {
        "treaty_id": str(treaty.id),
        "treaty_number": treaty.treaty_number,
        "reinsurer_name": treaty.reinsurer_name,
        "period_start": str(period_start) if period_start else None,
        "period_end": str(period_end) if period_end else None,
        "total_ceded_premium": str(total_ceded_premium),
        "total_ceded_limit": str(total_ceded_limit),
        "total_recoveries": str(total_recoveries),
        "cession_count": len(treaty_cessions),
        "recovery_count": len(treaty_recoveries),
        "cessions": treaty_cessions,
        "recoveries": treaty_recoveries,
    }

    logger.info(
        "reinsurance.bordereau_generated",
        treaty=treaty.treaty_number,
        cession_count=len(treaty_cessions),
        recovery_count=len(treaty_recoveries),
    )

    return bordereau
