"""Tests for openinsure.services.claims_service.ClaimsService."""

from unittest.mock import MagicMock, patch

import pytest

from openinsure.rbac.roles import Role
from openinsure.services.claims_service import ClaimsService

ADJUSTER = Role.CLAIMS_ADJUSTER  # "openinsure-claims-adjuster"


@pytest.fixture()
def mock_repo():
    with patch("openinsure.infrastructure.factory.get_claim_repository") as mock_factory:
        repo = MagicMock()
        mock_factory.return_value = repo
        yield repo


def _base_record(**overrides):
    rec = {
        "id": "claim-001",
        "status": "reported",
        "total_reserved": 0,
        "total_paid": 0,
        "reserves": [],
        "payments": [],
    }
    rec.update(overrides)
    return rec


class TestClaimsServiceSetReserve:
    async def test_set_reserve_success(self, mock_repo):
        svc = ClaimsService()
        record = _base_record()

        result = await svc.set_reserve(
            claim_id="claim-001",
            record=record,
            category="indemnity",
            amount=10000.0,
            currency="USD",
            notes="Initial reserve",
            user_role=ADJUSTER,
        )

        assert result["escalated"] is False
        assert result["reserve_id"] is not None
        assert result["total_reserved"] == 10000.0

    async def test_set_reserve_updates_total(self, mock_repo):
        svc = ClaimsService()
        record = _base_record()

        await svc.set_reserve("claim-001", record, "indemnity", 5000.0, "USD", None, ADJUSTER)
        result = await svc.set_reserve("claim-001", record, "expense", 3000.0, "USD", None, ADJUSTER)

        assert result["total_reserved"] == 8000.0
        assert len(record["reserves"]) == 2

    async def test_set_reserve_changes_status(self, mock_repo):
        svc = ClaimsService()
        record = _base_record(status="reported")

        await svc.set_reserve("claim-001", record, "indemnity", 10000.0, "USD", None, ADJUSTER)

        assert record["status"] == "reserved"

    async def test_set_reserve_escalation(self, mock_repo):
        svc = ClaimsService()
        record = _base_record()

        result = await svc.set_reserve(
            claim_id="claim-001",
            record=record,
            category="indemnity",
            amount=600000.0,
            currency="USD",
            notes="Large reserve",
            user_role=ADJUSTER,
        )

        assert result["escalated"] is True
        assert result["reserve_id"] is None


class TestClaimsServiceRecordPayment:
    async def test_record_payment_success(self, mock_repo):
        svc = ClaimsService()
        record = _base_record(status="reserved")

        result = await svc.record_payment(
            claim_id="claim-001",
            record=record,
            payee="vendor-001",
            amount=5000.0,
            currency="USD",
            category="indemnity",
            reference="REF-001",
            notes=None,
            user_role=ADJUSTER,
        )

        assert result["escalated"] is False
        assert result["payment_id"] is not None
        assert result["total_paid"] == 5000.0
        assert record["status"] == "approved"

    async def test_record_payment_escalation(self, mock_repo):
        svc = ClaimsService()
        record = _base_record(status="reserved")

        result = await svc.record_payment(
            claim_id="claim-001",
            record=record,
            payee="vendor-001",
            amount=500000.0,
            currency="USD",
            category="indemnity",
            reference=None,
            notes=None,
            user_role=ADJUSTER,
        )

        assert result["escalated"] is True
        assert result["payment_id"] is None


class TestClaimsServiceCloseClaim:
    async def test_close_claim_success(self, mock_repo):
        svc = ClaimsService()
        record = _base_record(status="approved", total_paid=5000.0)

        result = await svc.close_claim(
            claim_id="claim-001",
            record=record,
            reason="Settled",
            outcome="paid",
            user_role=ADJUSTER,
        )

        assert result["escalated"] is False
        assert result["closed_at"] is not None
        assert record["status"] == "closed"

    async def test_close_claim_escalation(self, mock_repo):
        svc = ClaimsService()
        record = _base_record(status="approved", total_paid=500000.0)

        result = await svc.close_claim(
            claim_id="claim-001",
            record=record,
            reason="Settled",
            outcome="paid",
            user_role=ADJUSTER,
        )

        assert result["escalated"] is True
        assert result["closed_at"] is None
