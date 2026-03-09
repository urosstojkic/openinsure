"""Tests for the Party domain entity."""

from uuid import uuid4

import pytest

from openinsure.domain.party import (
    Address,
    Contact,
    Party,
    PartyRole,
    PartyType,
    RiskProfile,
)


class TestCreateOrganizationParty:
    """Test creating an organization party."""

    def test_create_organization_party(self):
        party = Party(
            name="Acme Cyber Corp",
            party_type=PartyType.organization,
            tax_id="12-3456789",
        )
        assert party.name == "Acme Cyber Corp"
        assert party.party_type == PartyType.organization
        assert party.tax_id == "12-3456789"
        assert party.id is not None
        assert party.created_at is not None


class TestCreateIndividualParty:
    """Test creating an individual party."""

    def test_create_individual_party(self):
        party = Party(
            name="Jane Smith",
            party_type=PartyType.individual,
        )
        assert party.name == "Jane Smith"
        assert party.party_type == PartyType.individual
        assert party.roles == []
        assert party.addresses == []


class TestPartyWithMultipleRoles:
    """Test party with multiple roles."""

    def test_party_with_multiple_roles(self):
        party = Party(
            name="Multi-Role Corp",
            party_type=PartyType.organization,
            roles=[PartyRole.insured, PartyRole.claimant],
        )
        assert len(party.roles) == 2
        assert PartyRole.insured in party.roles
        assert PartyRole.claimant in party.roles

    def test_all_party_roles(self):
        party = Party(
            name="All Roles Corp",
            party_type=PartyType.organization,
            roles=list(PartyRole),
        )
        assert len(party.roles) == len(PartyRole)


class TestPartyWithAddresses:
    """Test party with addresses."""

    def test_party_with_addresses(self):
        address = Address(
            address_type="primary",
            street="123 Insurance Blvd",
            city="Hartford",
            state="CT",
            zip_code="06103",
        )
        party = Party(
            name="Addressed Corp",
            party_type=PartyType.organization,
            addresses=[address],
        )
        assert len(party.addresses) == 1
        assert party.addresses[0].city == "Hartford"
        assert party.addresses[0].country == "US"

    def test_party_with_multiple_addresses(self):
        mailing = Address(
            address_type="mailing",
            street="123 Main St",
            city="Hartford",
            state="CT",
            zip_code="06103",
        )
        billing = Address(
            address_type="billing",
            street="456 Oak Ave",
            city="Boston",
            state="MA",
            zip_code="02101",
        )
        party = Party(
            name="Multi-Address Corp",
            party_type=PartyType.organization,
            addresses=[mailing, billing],
        )
        assert len(party.addresses) == 2


class TestPartyValidationErrors:
    """Test party validation errors."""

    def test_missing_name_raises(self):
        with pytest.raises(Exception):
            Party(party_type=PartyType.organization)

    def test_missing_party_type_raises(self):
        with pytest.raises(Exception):
            Party(name="No Type Corp")

    def test_invalid_party_type_raises(self):
        with pytest.raises(Exception):
            Party(name="Bad Type", party_type="invalid_type")

    def test_invalid_role_raises(self):
        with pytest.raises(Exception):
            Party(
                name="Bad Role",
                party_type=PartyType.organization,
                roles=["not_a_role"],
            )


class TestPartySerialization:
    """Test party serialization."""

    def test_party_serialization(self):
        party = Party(
            name="Serialize Corp",
            party_type=PartyType.organization,
            roles=[PartyRole.insured],
            tax_id="98-7654321",
            addresses=[
                Address(
                    address_type="primary",
                    street="789 Test Ln",
                    city="Austin",
                    state="TX",
                    zip_code="73301",
                )
            ],
            contacts=[
                Contact(
                    contact_type="primary",
                    name="John Doe",
                    email="john@test.com",
                    phone="+1-555-1234",
                )
            ],
        )
        data = party.model_dump()
        assert data["name"] == "Serialize Corp"
        assert data["party_type"] == "organization"
        assert data["roles"] == ["insured"]
        assert len(data["addresses"]) == 1
        assert len(data["contacts"]) == 1

    def test_party_roundtrip(self):
        party = Party(
            name="Roundtrip Corp",
            party_type=PartyType.organization,
            roles=[PartyRole.broker],
        )
        data = party.model_dump()
        restored = Party(**data)
        assert restored.name == party.name
        assert restored.id == party.id
        assert restored.party_type == party.party_type


class TestPartyWithRiskProfile:
    """Test party with risk profile."""

    def test_party_with_risk_profile(self):
        profile = RiskProfile(
            line_of_business="cyber",
            risk_score=7.5,
            risk_factors={"industry": "technology", "revenue": "5M"},
        )
        party = Party(
            name="Profiled Corp",
            party_type=PartyType.organization,
            risk_profiles=[profile],
        )
        assert len(party.risk_profiles) == 1
        assert party.risk_profiles[0].risk_score == 7.5

    def test_party_with_relationships(self):
        parent_id = uuid4()
        party = Party(
            name="Child Corp",
            party_type=PartyType.organization,
            relationships={"parent_company": parent_id},
        )
        assert party.relationships["parent_company"] == parent_id
