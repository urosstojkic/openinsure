"""Reinsurance domain entities.

Carrier-only module — disabled in MGA deployments via deployment profile.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from openinsure.domain.common import DomainEntity, Money


class TreatyType(StrEnum):
    """Types of reinsurance treaty structures."""

    QUOTA_SHARE = "quota_share"
    EXCESS_OF_LOSS = "excess_of_loss"
    SURPLUS = "surplus"
    FACULTATIVE = "facultative"


class TreatyStatus(StrEnum):
    """Lifecycle status of a reinsurance treaty."""

    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"


class ReinsuranceContract(DomainEntity):
    """Reinsurance treaty/contract."""

    treaty_number: str
    treaty_type: TreatyType
    reinsurer_name: str
    status: TreatyStatus = TreatyStatus.ACTIVE
    effective_date: date
    expiration_date: date
    lines_of_business: list[str] = Field(default_factory=list)
    retention: Money = Decimal("0")
    limit: Money = Decimal("0")
    rate: Decimal = Decimal("0")
    capacity_total: Money = Decimal("0")
    capacity_used: Money = Decimal("0")
    reinstatements: int = 0
    description: str = ""


class CessionRecord(DomainEntity):
    """A cession of a policy to a treaty."""

    treaty_id: UUID
    policy_id: UUID
    policy_number: str
    ceded_premium: Money = Decimal("0")
    ceded_limit: Money = Decimal("0")
    cession_date: date | None = None


class RecoveryRecord(DomainEntity):
    """Reinsurance recovery on a claim."""

    treaty_id: UUID
    claim_id: UUID
    claim_number: str
    recovery_amount: Money = Decimal("0")
    recovery_date: date | None = None
    status: str = "pending"  # pending, billed, collected
