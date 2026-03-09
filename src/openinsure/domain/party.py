"""Party domain entities for OpenInsure.

Represents all parties involved in insurance transactions including
insureds, brokers, claimants, vendors, and adjusters.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from openinsure.domain.common import DomainEntity, Score


class PartyType(StrEnum):
    """Classification of a party."""

    individual = "individual"
    organization = "organization"


class PartyRole(StrEnum):
    """Role a party plays in insurance transactions."""

    insured = "insured"
    broker = "broker"
    agent = "agent"
    claimant = "claimant"
    vendor = "vendor"
    adjuster = "adjuster"


class Address(BaseModel):
    """Physical or mailing address."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    address_type: str = Field(..., description="Type of address: mailing, physical, billing")
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"


class Contact(BaseModel):
    """Contact information for a party."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    contact_type: str = Field(..., description="Type of contact: primary, billing, claims")
    name: str
    email: str
    phone: str | None = None


class RiskProfile(BaseModel):
    """Line-of-business-specific risk data associated with a party."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    line_of_business: str
    risk_score: Score
    risk_factors: dict[str, Any] = Field(default_factory=dict)
    last_assessed: datetime | None = None
    assessor: str | None = None


class Party(DomainEntity):
    """A party involved in insurance transactions.

    Parties can hold multiple roles (e.g. an organization can be both
    an insured and a claimant) and maintain relationships with other parties.
    """

    name: str
    party_type: PartyType
    roles: list[PartyRole] = Field(default_factory=list)
    tax_id: str | None = None
    registration_number: str | None = None
    addresses: list[Address] = Field(default_factory=list)
    contacts: list[Contact] = Field(default_factory=list)
    relationships: dict[str, UUID] = Field(
        default_factory=dict,
        description="Named relationships to other party IDs, e.g. {'parent_company': UUID}",
    )
    risk_profiles: list[RiskProfile] = Field(default_factory=list)
