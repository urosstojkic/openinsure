"""MGA/Delegated Authority domain entities."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from openinsure.domain.common import DomainEntity, Money


class DelegatedAuthority(DomainEntity):
    """Represents an MGA's delegated authority granted by the carrier."""

    mga_name: str
    mga_id: str
    status: str = "active"  # active, suspended, expired
    effective_date: date | None = None
    expiration_date: date | None = None
    lines_of_business: list[str] = Field(default_factory=list)
    premium_authority: Money = Decimal("0")
    premium_written: Money = Decimal("0")
    claims_authority: Money = Decimal("0")
    loss_ratio: Decimal = Decimal("0")
    compliance_score: Decimal = Decimal("100")
    last_audit_date: date | None = None


class BordereauRecord(DomainEntity):
    """A bordereau submission from an MGA for a given period."""

    mga_id: str
    period: str  # e.g., "2026-Q1"
    premium_reported: Money = Decimal("0")
    claims_reported: Money = Decimal("0")
    loss_ratio: Decimal = Decimal("0")
    policy_count: int = 0
    claim_count: int = 0
    status: str = "pending"  # pending, validated, exceptions, accepted
    exceptions: list[str] = Field(default_factory=list)
