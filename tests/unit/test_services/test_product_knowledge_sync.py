"""Tests for openinsure.services.product_knowledge_sync module."""

from unittest.mock import patch

import pytest

from openinsure.services.product_knowledge_sync import (
    ProductKnowledgeSyncService,
    SyncResult,
    _product_to_knowledge_document,
)


# ---------- SyncResult ----------


class TestSyncResult:
    def test_sync_result_initial_state(self):
        sr = SyncResult("prod-1", "CYBER-001")

        assert sr.product_id == "prod-1"
        assert sr.product_code == "CYBER-001"
        assert sr.cosmos_ok is False
        assert sr.search_ok is False
        assert sr.error is None

    def test_sync_result_to_dict(self):
        sr = SyncResult("prod-1", "CYBER-001")
        sr.cosmos_ok = True
        sr.search_ok = False
        sr.error = "Search sync failed (Cosmos succeeded)"

        d = sr.to_dict()

        assert d["product_id"] == "prod-1"
        assert d["product_code"] == "CYBER-001"
        assert d["cosmos"] == "ok"
        assert d["search"] == "failed"
        assert d["error"] == "Search sync failed (Cosmos succeeded)"


# ---------- _product_to_knowledge_document ----------


class TestProductToKnowledgeDocument:
    def test_basic_product(self):
        product = {
            "id": "p1",
            "code": "CYBER-001",
            "name": "Cyber Liability",
            "line_of_business": "cyber",
            "status": "active",
            "version": "2",
            "description": "Comprehensive cyber coverage",
        }

        doc = _product_to_knowledge_document(product)

        assert doc["id"] == "product-CYBER-001"
        assert doc["category"] == "product"
        assert doc["source"] == "product-management"
        assert "Cyber Liability" in doc["content"]
        assert doc["structured"]["code"] == "CYBER-001"
        assert doc["structured"]["status"] == "active"
        assert "last_updated" in doc

    def test_product_with_coverages(self):
        product = {
            "id": "p2",
            "code": "CYBER-002",
            "name": "Cyber Plus",
            "line_of_business": "cyber",
            "status": "active",
            "coverages": [
                {"name": "Data Breach", "default_limit": 1000000, "default_deductible": 25000},
                {"name": "Ransomware", "default_limit": 500000, "default_deductible": 10000},
            ],
        }

        doc = _product_to_knowledge_document(product)

        assert "Data Breach" in doc["content"]
        assert "Ransomware" in doc["content"]
        assert "Coverages:" in doc["content"]

    def test_product_with_rating_factors(self):
        product = {
            "id": "p3",
            "code": "CYBER-003",
            "name": "Cyber Advanced",
            "line_of_business": "cyber",
            "status": "active",
            "rating_factors": [
                {"name": "Revenue", "type": "numeric", "weight": 0.3},
                {"name": "Industry", "type": "categorical", "weight": 0.2},
            ],
        }

        doc = _product_to_knowledge_document(product)

        assert "Revenue" in doc["content"]
        assert "Rating Factors:" in doc["content"]


# ---------- ProductKnowledgeSyncService ----------


def _mock_settings():
    """Return settings with empty endpoints so no Azure clients are initialized."""
    from openinsure.config import Settings

    return Settings(
        cosmos_endpoint="",
        search_endpoint="",
        sql_connection_string="",
    )


class TestProductKnowledgeSyncService:
    async def test_sync_product_no_clients(self):
        with patch("openinsure.config.get_settings", return_value=_mock_settings()):
            svc = ProductKnowledgeSyncService()
            product = {
                "id": "p1",
                "code": "CYBER-001",
                "name": "Cyber Liability",
                "line_of_business": "cyber",
                "status": "active",
            }

            result = await svc.sync_product(product)

        assert result["product_id"] == "p1"
        assert result["cosmos"] == "failed"
        assert result["search"] == "failed"
        assert result["error"] is not None

    async def test_remove_product_no_clients(self):
        with patch("openinsure.config.get_settings", return_value=_mock_settings()):
            svc = ProductKnowledgeSyncService()

            removed = await svc.remove_product("p1")

        assert removed is False


# ---------- Additional Coverage Tests ----------

from unittest.mock import AsyncMock, MagicMock


class TestProductToKnowledgeDocumentRich:
    """Cover appetite_rules, authority_limits, territories, metadata text paths."""

    def test_product_with_appetite_rules(self):
        product = {
            "id": "p4",
            "code": "APT-001",
            "name": "Appetite Product",
            "status": "active",
            "appetite_rules": [
                {"field": "revenue", "operator": ">=", "value": "500000"},
                {"field": "employees", "operator": "<=", "value": "5000"},
            ],
        }
        doc = _product_to_knowledge_document(product)
        assert "Appetite Rules:" in doc["content"]
        assert "revenue >= 500000" in doc["content"]
        assert "employees <= 5000" in doc["content"]

    def test_product_with_authority_limits(self):
        product = {
            "id": "p5",
            "code": "AUTH-001",
            "name": "Authority Product",
            "status": "active",
            "authority_limits": {
                "auto_bind_max": 25000,
                "senior_uw_max": 100000,
            },
        }
        doc = _product_to_knowledge_document(product)
        assert "Authority Limits:" in doc["content"]
        assert "auto-bind" in doc["content"]
        assert "senior UW" in doc["content"]

    def test_product_with_metadata(self):
        product = {
            "id": "p7",
            "code": "META-001",
            "name": "Metadata Product",
            "status": "active",
            "metadata": {"tier": "standard", "channel": "direct"},
        }
        doc = _product_to_knowledge_document(product)
        assert "Product Metadata:" in doc["content"]
        assert "tier=standard" in doc["content"]
        assert "channel=direct" in doc["content"]

    def test_product_with_territories(self):
        product = {
            "id": "p6",
            "code": "TERR-001",
            "name": "Territory Product",
            "status": "active",
            "territories": ["US", "CA"],
        }
        doc = _product_to_knowledge_document(product)
        assert "Territories:" in doc["content"]
        assert "US" in doc["content"]
        assert "CA" in doc["content"]

    def test_full_product_document(self):
        product = {
            "id": "prod-1",
            "code": "CYBER-001",
            "name": "Cyber Insurance",
            "line_of_business": "cyber",
            "status": "published",
            "version": "2",
            "description": "Comprehensive cyber coverage",
            "coverages": [
                {"name": "Breach Response", "default_limit": 1000000, "default_deductible": 10000},
                {"name": "Business Interruption", "default_limit": 500000, "default_deductible": 5000},
            ],
            "rating_factors": [
                {"name": "Employee Count", "type": "numeric", "weight": 0.3},
                {"name": "Industry", "type": "categorical", "weight": 0.5},
            ],
            "appetite_rules": [
                {"field": "revenue", "operator": ">=", "value": "500000"},
                {"field": "employees", "operator": "<=", "value": "5000"},
            ],
            "authority_limits": {"auto_bind_max": 25000, "senior_uw_max": 100000},
            "territories": ["US", "CA"],
            "metadata": {"tier": "standard", "channel": "direct"},
        }
        doc = _product_to_knowledge_document(product)
        assert doc["id"] == "product-CYBER-001"
        assert doc["category"] == "product"
        assert "Breach Response" in doc["content"]
        assert "Business Interruption" in doc["content"]
        assert "Employee Count" in doc["content"]
        assert "revenue" in doc["content"]
        assert "US" in doc["content"]
        assert "tier=standard" in doc["content"]

    def test_product_with_relational_data(self):
        product = {"id": "prod-1", "code": "REL-001", "name": "Relational Product", "status": "published"}
        rel_coverages = [{"name": "Coverage A", "default_limit": 1000000, "default_deductible": 5000}]
        rel_factors = [{"name": "Factor A", "type": "numeric", "weight": 0.5}]
        rel_rules = [{"field": "industry", "operator": "in", "value": "tech"}]
        doc = _product_to_knowledge_document(
            product,
            relational_coverages=rel_coverages,
            relational_factors=rel_factors,
            relational_rules=rel_rules,
        )
        assert doc["id"] == "product-REL-001"
        assert doc["category"] == "product"


class TestSyncResultExtended:
    def test_sync_result_both_success(self):
        sr = SyncResult("prod-1", "CYBER-001")
        sr.cosmos_ok = True
        sr.search_ok = True
        d = sr.to_dict()
        assert d["cosmos"] == "ok"
        assert d["search"] == "ok"
        assert d["error"] is None

    def test_sync_result_cosmos_only(self):
        sr = SyncResult("prod-1", "CYBER-001")
        sr.cosmos_ok = True
        sr.search_ok = False
        sr.error = "Search sync failed"
        d = sr.to_dict()
        assert d["cosmos"] == "ok"
        assert d["search"] == "failed"
        assert d["error"] == "Search sync failed"


class TestInitClients:
    def test_init_clients_early_return(self):
        """Second call to _init_clients is a no-op (covers line 201)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True
        svc._init_clients()
        assert svc._cosmos is None
        assert svc._search is None

    def test_init_clients_cosmos_connection(self):
        """_init_clients tries to connect to Cosmos when endpoint is set (covers 210-226)."""
        svc = ProductKnowledgeSyncService()
        mock_settings = MagicMock()
        mock_settings.cosmos_endpoint = "https://fake.documents.azure.com"
        mock_settings.cosmos_database_name = "test-db"
        mock_settings.search_endpoint = ""

        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.get_database_client.return_value = mock_db

        with patch("openinsure.config.get_settings", return_value=mock_settings), \
             patch("azure.cosmos.CosmosClient", return_value=mock_client), \
             patch("azure.identity.DefaultAzureCredential", return_value=MagicMock()):
            svc._init_clients()

        assert svc._initialised is True
        assert svc._cosmos is mock_db

    def test_init_clients_search_connection(self):
        """_init_clients tries to connect to Search when endpoint is set (covers 230-242)."""
        svc = ProductKnowledgeSyncService()
        mock_settings = MagicMock()
        mock_settings.cosmos_endpoint = ""
        mock_settings.search_endpoint = "https://fake.search.windows.net"
        mock_settings.search_index_name = "test-index"

        mock_search_client = MagicMock()

        with patch("openinsure.config.get_settings", return_value=mock_settings), \
             patch("azure.identity.DefaultAzureCredential", return_value=MagicMock()), \
             patch("azure.search.documents.SearchClient", return_value=mock_search_client):
            svc._init_clients()

        assert svc._initialised is True
        assert svc._search is mock_search_client

    def test_init_clients_cosmos_exception(self):
        """Cosmos init failure is caught gracefully (covers except branch on 226)."""
        svc = ProductKnowledgeSyncService()
        mock_settings = MagicMock()
        mock_settings.cosmos_endpoint = "https://fake.documents.azure.com"
        mock_settings.search_endpoint = ""

        with patch("openinsure.config.get_settings", return_value=mock_settings), \
             patch("azure.identity.DefaultAzureCredential", side_effect=Exception("no creds")):
            svc._init_clients()

        assert svc._initialised is True
        assert svc._cosmos is None

    def test_init_clients_search_exception(self):
        """Search init failure is caught gracefully (covers except branch on 242)."""
        svc = ProductKnowledgeSyncService()
        mock_settings = MagicMock()
        mock_settings.cosmos_endpoint = ""
        mock_settings.search_endpoint = "https://fake.search.windows.net"

        with patch("openinsure.config.get_settings", return_value=mock_settings), \
             patch("azure.identity.DefaultAzureCredential", side_effect=Exception("no creds")):
            svc._init_clients()

        assert svc._initialised is True
        assert svc._search is None


class TestSyncProductWithClients:
    @pytest.mark.asyncio
    async def test_sync_product_cosmos_and_search_success(self):
        """sync_product with both clients succeeding (covers 287-313, 317-340)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_container = MagicMock()
        mock_cosmos = MagicMock()
        mock_cosmos.get_container_client.return_value = mock_container
        svc._cosmos = mock_cosmos

        mock_search_result = MagicMock()
        mock_search_result.succeeded = True
        mock_search = MagicMock()
        mock_search.upload_documents.return_value = [mock_search_result]
        svc._search = mock_search

        product = {"id": "p1", "code": "TEST-001", "name": "Test", "status": "active"}

        with patch(
            "openinsure.infrastructure.factory.get_product_relations_repository",
            return_value=None,
        ):
            result = await svc.sync_product(product)

        assert result["cosmos"] == "ok"
        assert result["search"] == "ok"
        assert result["error"] is None
        mock_container.upsert_item.assert_called_once()
        mock_search.upload_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_product_cosmos_ok_search_failed(self):
        """Cosmos succeeds but Search fails — partial error message (covers 346-347)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_container = MagicMock()
        mock_cosmos = MagicMock()
        mock_cosmos.get_container_client.return_value = mock_container
        svc._cosmos = mock_cosmos

        mock_search = MagicMock()
        mock_search.upload_documents.side_effect = Exception("search down")
        svc._search = mock_search

        product = {"id": "p1", "code": "TEST-002", "name": "Test", "status": "active"}

        with patch(
            "openinsure.infrastructure.factory.get_product_relations_repository",
            return_value=None,
        ):
            result = await svc.sync_product(product)

        assert result["cosmos"] == "ok"
        assert result["search"] == "failed"
        assert "Search sync failed" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_product_cosmos_failed_search_ok(self):
        """Cosmos fails but Search succeeds — partial error message (covers 344-345)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = Exception("cosmos down")
        mock_cosmos = MagicMock()
        mock_cosmos.get_container_client.return_value = mock_container
        svc._cosmos = mock_cosmos

        mock_search_result = MagicMock()
        mock_search_result.succeeded = True
        mock_search = MagicMock()
        mock_search.upload_documents.return_value = [mock_search_result]
        svc._search = mock_search

        product = {"id": "p1", "code": "TEST-003", "name": "Test", "status": "active"}

        with patch(
            "openinsure.infrastructure.factory.get_product_relations_repository",
            return_value=None,
        ):
            result = await svc.sync_product(product)

        assert result["cosmos"] == "failed"
        assert result["search"] == "ok"
        assert "Cosmos sync failed" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_product_with_relational_data(self):
        """sync_product loads relational data when repository is available (covers 273-274)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True
        svc._cosmos = None
        svc._search = None

        mock_relations = AsyncMock()
        mock_relations.get_coverages.return_value = [
            {"name": "Cov A", "default_limit": 100000, "default_deductible": 1000}
        ]
        mock_relations.get_rating_factors.return_value = [
            {"name": "Factor A", "type": "numeric", "weight": 0.5}
        ]
        mock_relations.get_appetite_rules.return_value = [
            {"field": "industry", "operator": "in", "value": "tech"}
        ]

        product = {"id": "p1", "code": "REL-001", "name": "Test", "status": "active"}

        with patch(
            "openinsure.infrastructure.factory.get_product_relations_repository",
            return_value=mock_relations,
        ):
            result = await svc.sync_product(product)

        mock_relations.get_coverages.assert_awaited_once_with("p1")
        mock_relations.get_rating_factors.assert_awaited_once_with("p1")
        mock_relations.get_appetite_rules.assert_awaited_once_with("p1")
        assert result["product_id"] == "p1"


class TestRemoveProductWithClients:
    @pytest.mark.asyncio
    async def test_remove_product_cosmos_and_search(self):
        """remove_product deletes from both stores (covers 368-386, 389-394)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_container = MagicMock()
        mock_container.query_items.return_value = [
            {"id": "product-p1", "category": "product"},
        ]
        mock_cosmos = MagicMock()
        mock_cosmos.get_container_client.return_value = mock_container
        svc._cosmos = mock_cosmos

        mock_search = MagicMock()
        svc._search = mock_search

        removed = await svc.remove_product("p1")

        assert removed is True
        mock_container.delete_item.assert_called_once_with("product-p1", partition_key="product")
        mock_search.delete_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_product_cosmos_exception(self):
        """Cosmos failure during remove is caught (covers except on 386)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_container = MagicMock()
        mock_container.query_items.side_effect = Exception("cosmos error")
        mock_cosmos = MagicMock()
        mock_cosmos.get_container_client.return_value = mock_container
        svc._cosmos = mock_cosmos
        svc._search = None

        removed = await svc.remove_product("p1")
        assert removed is False

    @pytest.mark.asyncio
    async def test_remove_product_search_exception(self):
        """Search failure during remove is caught (covers except on 394)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True
        svc._cosmos = None

        mock_search = MagicMock()
        mock_search.delete_documents.side_effect = Exception("search error")
        svc._search = mock_search

        removed = await svc.remove_product("p1")
        assert removed is False

    @pytest.mark.asyncio
    async def test_remove_product_search_success_only(self):
        """Remove succeeds in Search when Cosmos is not configured."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True
        svc._cosmos = None

        mock_search = MagicMock()
        svc._search = mock_search

        removed = await svc.remove_product("p1")
        assert removed is True
        mock_search.delete_documents.assert_called_once()


class TestSyncAllProducts:
    @pytest.mark.asyncio
    async def test_sync_all_products(self):
        """sync_all_products iterates all products from repo (covers 407-435)."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = [
            {"id": "p1", "code": "T1", "name": "Test 1", "status": "active"},
            {"id": "p2", "code": "T2", "name": "Test 2", "status": "active"},
        ]

        with patch(
            "openinsure.infrastructure.factory.get_product_repository",
            return_value=mock_repo,
        ), patch.object(svc, "sync_product", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"cosmos": "ok", "search": "ok", "error": None}
            summary = await svc.sync_all_products()

        assert summary["total_products"] == 2
        assert summary["cosmos_synced"] == 2
        assert summary["search_synced"] == 2
        assert summary["errors"] == 0
        assert len(summary["details"]) == 2

    @pytest.mark.asyncio
    async def test_sync_all_products_with_errors(self):
        """sync_all_products counts errors correctly."""
        svc = ProductKnowledgeSyncService()
        svc._initialised = True

        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = [
            {"id": "p1", "code": "T1", "name": "Test 1", "status": "active"},
            {"id": "p2", "code": "T2", "name": "Test 2", "status": "active"},
        ]

        with patch(
            "openinsure.infrastructure.factory.get_product_repository",
            return_value=mock_repo,
        ), patch.object(svc, "sync_product", new_callable=AsyncMock) as mock_sync:
            mock_sync.side_effect = [
                {"cosmos": "ok", "search": "ok", "error": None},
                {"cosmos": "failed", "search": "failed", "error": "Both failed"},
            ]
            summary = await svc.sync_all_products()

        assert summary["total_products"] == 2
        assert summary["cosmos_synced"] == 1
        assert summary["search_synced"] == 1
        assert summary["errors"] == 1
