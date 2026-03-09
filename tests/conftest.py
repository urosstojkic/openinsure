"""Shared test fixtures for OpenInsure test suite."""

import pytest

# Register test mode plugin (--azure flag, azure_mode/storage_mode fixtures)
pytest_plugins = ["tests.conftest_modes"]


@pytest.fixture
def sample_party_data() -> dict:
    """Sample party data for testing."""
    return {
        "name": "Acme Cyber Corp",
        "party_type": "organization",
        "tax_id": "12-3456789",
        "addresses": [
            {
                "address_type": "primary",
                "street": "123 Insurance Blvd",
                "city": "Hartford",
                "state": "CT",
                "zip_code": "06103",
                "country": "US",
            }
        ],
        "contacts": [
            {
                "contact_type": "primary",
                "name": "Jane Smith",
                "email": "jane.smith@acmecyber.com",
                "phone": "+1-555-0100",
            }
        ],
    }


@pytest.fixture
def sample_submission_data(sample_party_data: dict) -> dict:
    """Sample cyber insurance submission data for testing."""
    return {
        "channel": "email",
        "line_of_business": "cyber",
        "applicant": sample_party_data,
        "requested_effective_date": "2026-07-01",
        "requested_expiration_date": "2027-07-01",
        "cyber_risk_data": {
            "annual_revenue": 5000000,
            "employee_count": 50,
            "industry_sic_code": "7372",
            "security_maturity_score": 3.5,
            "has_mfa": True,
            "has_endpoint_protection": True,
            "has_backup_strategy": True,
            "prior_incidents": 0,
        },
    }
