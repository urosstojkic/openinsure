"""Common domain types and base classes for OpenInsure."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(UTC)


def new_id() -> UUID:
    """Generate a new UUID4."""
    return uuid4()


# Type aliases for domain clarity
Money = Annotated[Decimal, Field(ge=0, decimal_places=2)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, decimal_places=4)]
Score = Annotated[float, Field(ge=0.0, le=10.0)]
ConfidenceScore = Annotated[float, Field(ge=0.0, le=1.0)]


class DomainEntity(BaseModel):
    """Base class for all domain entities."""

    model_config = ConfigDict(
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
        ser_json_timedelta="iso8601",
    )

    id: UUID = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
