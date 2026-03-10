"""Actuarial domain entities."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from openinsure.domain.common import DomainEntity, Money


class ReserveType(StrEnum):
    CASE = "case"
    IBNR = "ibnr"
    BULK = "bulk"


class ActuarialReserve(DomainEntity):
    """Actuarial reserve for a line of business / accident year."""

    line_of_business: str
    accident_year: int
    reserve_type: ReserveType
    carried_amount: Money = Decimal("0")
    indicated_amount: Money = Decimal("0")
    selected_amount: Money = Decimal("0")
    as_of_date: date | None = None
    analyst: str = ""
    approved_by: str = ""
    notes: str = ""


class LossTriangleEntry(DomainEntity):
    """Single cell in a loss development triangle."""

    line_of_business: str
    accident_year: int
    development_month: int
    paid_amount: Money = Decimal("0")
    incurred_amount: Money = Decimal("0")
    case_reserve: Money = Decimal("0")
    claim_count: int = 0


class RateIndication(DomainEntity):
    """Rate adequacy indication for a segment."""

    line_of_business: str
    segment: str  # e.g., "cyber-smb-healthcare"
    current_rate: Decimal = Decimal("0")
    indicated_rate: Decimal = Decimal("0")
    adequacy_ratio: Decimal = Decimal("0")  # indicated/current
    effective_date: date | None = None
    notes: str = ""
