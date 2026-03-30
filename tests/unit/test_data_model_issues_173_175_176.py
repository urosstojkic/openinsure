"""Tests for policy transactions, polymorphic documents, and work items.

Covers the three data model issues #173, #175, #176.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import pytest

from openinsure.services import policy_transaction_service, work_item_service

# ---------------------------------------------------------------------------
# #173 — Policy Transaction Service
# ---------------------------------------------------------------------------


class TestPolicyTransactionService:
    """Tests for the policy_transaction_service module."""

    @pytest.fixture(autouse=True)
    def _clear(self):
        """Clear in-memory transaction store between tests."""
        policy_transaction_service._transactions.clear()
        yield
        policy_transaction_service._transactions.clear()

    @pytest.mark.asyncio
    async def test_record_new_business_transaction(self):
        policy_id = str(uuid4())
        txn = await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="new_business",
            effective_date=date(2026, 1, 1),
            expiration_date=date(2027, 1, 1),
            premium_change=15000.00,
            description="New cyber liability policy",
        )
        assert txn["transaction_type"] == "new_business"
        assert txn["policy_id"] == policy_id
        assert txn["premium_change"] == 15000.00
        assert txn["effective_date"] == "2026-01-01"

    @pytest.mark.asyncio
    async def test_record_endorsement_with_snapshot(self):
        policy_id = str(uuid4())
        coverages = [
            {"coverage_code": "CYB-001", "coverage_name": "Cyber Liability", "limit": 1000000},
        ]
        txn = await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="endorsement",
            effective_date=date(2026, 6, 1),
            premium_change=2000.00,
            description="Add ransomware coverage",
            coverages_snapshot=coverages,
        )
        assert txn["transaction_type"] == "endorsement"
        snapshot = json.loads(txn["coverages_snapshot"])
        assert len(snapshot) == 1
        assert snapshot[0]["coverage_code"] == "CYB-001"

    @pytest.mark.asyncio
    async def test_record_renewal_transaction(self):
        policy_id = str(uuid4())
        txn = await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="renewal",
            effective_date=date(2027, 1, 1),
            expiration_date=date(2028, 1, 1),
            premium_change=15000.00,
            description="Renewal of POL-12345678",
        )
        assert txn["transaction_type"] == "renewal"
        assert txn["expiration_date"] == "2028-01-01"

    @pytest.mark.asyncio
    async def test_record_cancellation_transaction(self):
        policy_id = str(uuid4())
        txn = await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="cancellation",
            effective_date=date(2026, 6, 15),
            premium_change=-7500.00,
            description="Insured request",
        )
        assert txn["transaction_type"] == "cancellation"
        assert txn["premium_change"] == -7500.00

    @pytest.mark.asyncio
    async def test_get_transactions_returns_ordered(self):
        policy_id = str(uuid4())
        await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="new_business",
            effective_date=date(2026, 1, 1),
            premium_change=15000.00,
        )
        await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="endorsement",
            effective_date=date(2026, 6, 1),
            premium_change=2000.00,
        )
        txns = await policy_transaction_service.get_transactions(policy_id)
        assert len(txns) == 2
        assert txns[0]["effective_date"] <= txns[1]["effective_date"]

    @pytest.mark.asyncio
    async def test_get_transactions_filters_by_policy(self):
        p1 = str(uuid4())
        p2 = str(uuid4())
        await policy_transaction_service.record_transaction(
            policy_id=p1,
            transaction_type="new_business",
            effective_date=date(2026, 1, 1),
            premium_change=10000.0,
        )
        await policy_transaction_service.record_transaction(
            policy_id=p2,
            transaction_type="new_business",
            effective_date=date(2026, 1, 1),
            premium_change=20000.0,
        )
        txns = await policy_transaction_service.get_transactions(p1)
        assert len(txns) == 1
        assert txns[0]["policy_id"] == p1

    @pytest.mark.asyncio
    async def test_get_transaction_by_id(self):
        policy_id = str(uuid4())
        txn = await policy_transaction_service.record_transaction(
            policy_id=policy_id,
            transaction_type="new_business",
            effective_date=date(2026, 1, 1),
            premium_change=15000.00,
        )
        found = await policy_transaction_service.get_transaction_by_id(txn["id"])
        assert found is not None
        assert found["id"] == txn["id"]

    @pytest.mark.asyncio
    async def test_get_transaction_by_id_not_found(self):
        found = await policy_transaction_service.get_transaction_by_id("nonexistent")
        assert found is None


# ---------------------------------------------------------------------------
# #176 — Work Item Service
# ---------------------------------------------------------------------------


class TestWorkItemService:
    """Tests for the work_item_service module."""

    @pytest.fixture(autouse=True)
    def _clear(self):
        """Clear in-memory work item store between tests."""
        work_item_service._work_items.clear()
        yield
        work_item_service._work_items.clear()

    @pytest.mark.asyncio
    async def test_create_work_item(self):
        item = await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="underwriting_review",
            title="Review cyber policy submission",
            assigned_to="john.doe@example.com",
            priority="high",
        )
        assert item["work_type"] == "underwriting_review"
        assert item["status"] == "open"
        assert item["priority"] == "high"
        assert item["assigned_to"] == "john.doe@example.com"

    @pytest.mark.asyncio
    async def test_create_work_item_with_sla(self):
        item = await work_item_service.create_work_item(
            entity_type="claim",
            entity_id=str(uuid4()),
            work_type="claims_review",
            title="Review claim evidence",
            assigned_to="adjuster@example.com",
            sla_hours=24,
        )
        assert item["sla_hours"] == 24
        assert item["due_date"] is not None  # Auto-calculated from SLA

    @pytest.mark.asyncio
    async def test_create_work_item_invalid_priority(self):
        with pytest.raises(ValueError, match="Invalid priority"):
            await work_item_service.create_work_item(
                entity_type="policy",
                entity_id=str(uuid4()),
                work_type="review",
                title="Test",
                priority="critical",  # Invalid
            )

    @pytest.mark.asyncio
    async def test_complete_work_item(self):
        item = await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="review",
            title="Review policy",
            assigned_to="user@example.com",
        )
        completed = await work_item_service.complete_work_item(item["id"], "reviewer@example.com")
        assert completed is not None
        assert completed["status"] == "completed"
        assert completed["completed_by"] == "reviewer@example.com"
        assert completed["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_complete_already_completed_raises(self):
        item = await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="review",
            title="Review policy",
        )
        await work_item_service.complete_work_item(item["id"], "user1")
        with pytest.raises(ValueError, match="already completed"):
            await work_item_service.complete_work_item(item["id"], "user2")

    @pytest.mark.asyncio
    async def test_complete_nonexistent_returns_none(self):
        result = await work_item_service.complete_work_item("nonexistent", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_inbox(self):
        user = "uw@example.com"
        await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="review",
            title="Task 1",
            assigned_to=user,
        )
        await work_item_service.create_work_item(
            entity_type="claim",
            entity_id=str(uuid4()),
            work_type="review",
            title="Task 2",
            assigned_to=user,
        )
        await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="review",
            title="Task 3",
            assigned_to="other@example.com",
        )
        inbox = await work_item_service.get_inbox(user)
        assert len(inbox) == 2
        assert all(i["assigned_to"] == user for i in inbox)

    @pytest.mark.asyncio
    async def test_get_inbox_excludes_completed(self):
        user = "uw@example.com"
        item = await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="review",
            title="Task 1",
            assigned_to=user,
        )
        await work_item_service.complete_work_item(item["id"], "reviewer")
        inbox = await work_item_service.get_inbox(user)
        assert len(inbox) == 0

    @pytest.mark.asyncio
    async def test_get_work_item_by_id(self):
        item = await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=str(uuid4()),
            work_type="review",
            title="Test",
        )
        found = await work_item_service.get_work_item_by_id(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    @pytest.mark.asyncio
    async def test_list_work_items_with_filters(self):
        entity_id = str(uuid4())
        await work_item_service.create_work_item(
            entity_type="policy",
            entity_id=entity_id,
            work_type="review",
            title="Policy task",
        )
        await work_item_service.create_work_item(
            entity_type="claim",
            entity_id=str(uuid4()),
            work_type="review",
            title="Claim task",
        )
        items = await work_item_service.list_work_items(entity_type="policy")
        assert len(items) == 1
        assert items[0]["entity_type"] == "policy"


# ---------------------------------------------------------------------------
# #175 — Document records (in-memory, tested via API below)
# ---------------------------------------------------------------------------


class TestDocumentRecords:
    """Tests for the document record CRUD in documents API."""

    @pytest.fixture
    def client(self):
        """Create a TestClient for the app."""
        from starlette.testclient import TestClient

        from openinsure.main import create_app

        app = create_app()
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _clear(self):
        """Clear in-memory document records between tests."""
        from openinsure.api.documents import _document_records

        _document_records.clear()
        yield
        _document_records.clear()

    def test_create_document_record(self, client):
        resp = client.post(
            "/api/v1/documents/records",
            json={
                "entity_type": "submission",
                "entity_id": str(uuid4()),
                "document_type": "application_form",
                "filename": "acme-application.pdf",
                "uploaded_by": "broker@example.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entity_type"] == "submission"
        assert data["filename"] == "acme-application.pdf"
        assert data["uploaded_by"] == "broker@example.com"
        assert data["deleted_at"] is None

    def test_list_document_records(self, client):
        entity_id = str(uuid4())
        for i in range(3):
            client.post(
                "/api/v1/documents/records",
                json={
                    "entity_type": "policy",
                    "entity_id": entity_id,
                    "document_type": "declaration",
                    "filename": f"dec-page-{i}.pdf",
                },
            )
        resp = client.get(f"/api/v1/documents/records?entity_type=policy&entity_id={entity_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_get_document_record(self, client):
        create_resp = client.post(
            "/api/v1/documents/records",
            json={
                "entity_type": "claim",
                "entity_id": str(uuid4()),
                "document_type": "loss_report",
                "filename": "loss-report.pdf",
            },
        )
        doc_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/documents/records/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id

    def test_get_document_record_not_found(self, client):
        resp = client.get(f"/api/v1/documents/records/{uuid4()}")
        assert resp.status_code == 404

    def test_update_document_record(self, client):
        create_resp = client.post(
            "/api/v1/documents/records",
            json={
                "entity_type": "policy",
                "entity_id": str(uuid4()),
                "document_type": "certificate",
                "filename": "cert.pdf",
            },
        )
        doc_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/v1/documents/records/{doc_id}",
            json={
                "document_type": "endorsement_form",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "endorsement_form"

    def test_soft_delete_document_record(self, client):
        create_resp = client.post(
            "/api/v1/documents/records",
            json={
                "entity_type": "submission",
                "entity_id": str(uuid4()),
                "document_type": "application_form",
                "filename": "app.pdf",
            },
        )
        doc_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/documents/records/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted_at"] is not None

        # Verify it's excluded from default listing
        list_resp = client.get("/api/v1/documents/records")
        assert all(d["id"] != doc_id for d in list_resp.json()["items"])

        # But included with include_deleted=true
        list_resp = client.get("/api/v1/documents/records?include_deleted=true")
        found = [d for d in list_resp.json()["items"] if d["id"] == doc_id]
        assert len(found) == 1

    def test_delete_already_deleted_returns_409(self, client):
        create_resp = client.post(
            "/api/v1/documents/records",
            json={
                "entity_type": "policy",
                "entity_id": str(uuid4()),
                "document_type": "certificate",
                "filename": "cert.pdf",
            },
        )
        doc_id = create_resp.json()["id"]
        client.delete(f"/api/v1/documents/records/{doc_id}")
        resp = client.delete(f"/api/v1/documents/records/{doc_id}")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# #176 — Work Items API
# ---------------------------------------------------------------------------


class TestWorkItemsAPI:
    """Integration tests for work items API endpoints."""

    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient

        from openinsure.main import create_app

        app = create_app()
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _clear(self):
        work_item_service._work_items.clear()
        yield
        work_item_service._work_items.clear()

    def test_create_work_item_endpoint(self, client):
        resp = client.post(
            "/api/v1/work-items",
            json={
                "entity_type": "submission",
                "entity_id": str(uuid4()),
                "work_type": "underwriting_review",
                "title": "Review Acme Corp submission",
                "assigned_to": "uw@example.com",
                "priority": "high",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["work_type"] == "underwriting_review"
        assert data["status"] == "open"

    def test_list_work_items_by_assigned_to(self, client):
        user = "uw@example.com"
        for i in range(3):
            client.post(
                "/api/v1/work-items",
                json={
                    "entity_type": "policy",
                    "entity_id": str(uuid4()),
                    "work_type": "review",
                    "title": f"Task {i}",
                    "assigned_to": user,
                },
            )
        resp = client.get(f"/api/v1/work-items?assigned_to={user}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_complete_work_item_endpoint(self, client):
        create_resp = client.post(
            "/api/v1/work-items",
            json={
                "entity_type": "claim",
                "entity_id": str(uuid4()),
                "work_type": "claims_review",
                "title": "Review claim",
                "assigned_to": "adjuster@example.com",
            },
        )
        item_id = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/work-items/{item_id}/complete",
            json={
                "completed_by": "adjuster@example.com",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_complete_nonexistent_returns_404(self, client):
        resp = client.post(
            f"/api/v1/work-items/{uuid4()}/complete",
            json={
                "completed_by": "user@example.com",
            },
        )
        assert resp.status_code == 404

    def test_get_work_item_endpoint(self, client):
        create_resp = client.post(
            "/api/v1/work-items",
            json={
                "entity_type": "policy",
                "entity_id": str(uuid4()),
                "work_type": "review",
                "title": "Test item",
            },
        )
        item_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/work-items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id


# ---------------------------------------------------------------------------
# #173 — Policy Transactions API
# ---------------------------------------------------------------------------


class TestPolicyTransactionsAPI:
    """Integration tests for the GET /policies/{id}/transactions endpoint."""

    @pytest.fixture
    def client(self):
        from unittest.mock import patch

        from starlette.testclient import TestClient

        from openinsure.infrastructure.repositories.policies import InMemoryPolicyRepository
        from openinsure.main import create_app

        mem_repo = InMemoryPolicyRepository()
        with patch("openinsure.api.policies._repo", mem_repo):
            app = create_app()
            yield TestClient(app)

    @pytest.fixture(autouse=True)
    def _clear(self):
        policy_transaction_service._transactions.clear()
        yield
        policy_transaction_service._transactions.clear()

    def test_transactions_endpoint_returns_empty_list(self, client):
        # Create a policy first
        create_resp = client.post(
            "/api/v1/policies",
            json={
                "submission_id": str(uuid4()),
                "product_id": "cyber-001",
                "policyholder_name": "Acme Corp",
                "effective_date": "2026-01-01T00:00:00+00:00",
                "expiration_date": "2027-01-01T00:00:00+00:00",
                "premium": 15000.0,
            },
        )
        policy_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/policies/{policy_id}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["policy_id"] == policy_id
        assert data["total"] == 0
        assert data["items"] == []

    def test_transactions_endpoint_after_recording(self, client):
        # Create a policy
        create_resp = client.post(
            "/api/v1/policies",
            json={
                "submission_id": str(uuid4()),
                "product_id": "cyber-001",
                "policyholder_name": "Test Corp",
                "effective_date": "2026-01-01T00:00:00+00:00",
                "expiration_date": "2027-01-01T00:00:00+00:00",
                "premium": 10000.0,
            },
        )
        policy_id = create_resp.json()["id"]

        # Manually record a transaction
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            policy_transaction_service.record_transaction(
                policy_id=policy_id,
                transaction_type="new_business",
                effective_date="2026-01-01",
                premium_change=10000.0,
                description="New business",
            )
        )

        resp = client.get(f"/api/v1/policies/{policy_id}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["transaction_type"] == "new_business"

    def test_transactions_endpoint_policy_not_found(self, client):
        resp = client.get(f"/api/v1/policies/{uuid4()}/transactions")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Escalation → Work Item integration
# ---------------------------------------------------------------------------


class TestEscalationWorkItemIntegration:
    """Verify that creating an escalation also creates a work item."""

    @pytest.fixture(autouse=True)
    def _clear(self):
        from openinsure.services.escalation import _escalation_queue

        _escalation_queue.clear()
        work_item_service._work_items.clear()
        yield
        _escalation_queue.clear()
        work_item_service._work_items.clear()

    @pytest.mark.asyncio
    async def test_escalation_creates_work_item(self):
        from openinsure.services.escalation import escalate

        entity_id = str(uuid4())
        await escalate(
            action="bind_policy",
            entity_type="policy",
            entity_id=entity_id,
            requested_by="analyst@example.com",
            requested_role="openinsure-uw-analyst",
            amount=500000.0,
            authority_result={
                "required_role": "CUO",
                "escalation_chain": ["CUO"],
                "reason": "Amount exceeds analyst authority",
            },
        )

        # Verify work item was created
        items = await work_item_service.list_work_items(entity_id=entity_id)
        assert len(items) == 1
        assert items[0]["work_type"] == "escalation_review"
        assert items[0]["priority"] == "high"
        assert "CUO" in items[0]["title"]
