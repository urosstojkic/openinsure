"""Azure resource connectivity tests.

These tests verify that Azure resources are reachable and properly configured.
Only run with the --azure flag: pytest tests/ --azure -v
"""

import pytest

from openinsure.config import get_settings


@pytest.mark.azure
class TestAzureConnectivity:
    """Tests that verify Azure resources are reachable. Run with: pytest --azure"""

    def test_sql_connection(self, azure_mode):
        """Test Azure SQL Database connectivity."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        settings = get_settings()
        assert settings.sql_connection_string, "OPENINSURE_SQL_CONNECTION_STRING must be set"
        import pyodbc

        conn = pyodbc.connect(settings.sql_connection_string, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        conn.close()

    def test_cosmos_connection(self, azure_mode):
        """Test Azure Cosmos DB connectivity."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        settings = get_settings()
        assert settings.cosmos_endpoint, "OPENINSURE_COSMOS_ENDPOINT must be set"
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        client = CosmosClient(settings.cosmos_endpoint, credential=credential)
        # Verify we can list databases (proves connectivity)
        list(client.list_databases())

    def test_blob_storage_connection(self, azure_mode):
        """Test Azure Blob Storage connectivity."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        settings = get_settings()
        assert settings.storage_account_url, "OPENINSURE_STORAGE_ACCOUNT_URL must be set"
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        credential = DefaultAzureCredential()
        client = BlobServiceClient(settings.storage_account_url, credential=credential)
        # Verify we can list containers (proves connectivity)
        list(client.list_containers(max_results=1))

    def test_openai_endpoint(self, azure_mode):
        """Test Azure AI / Foundry endpoint connectivity."""
        if not azure_mode:
            pytest.skip("Requires --azure flag")
        settings = get_settings()
        assert settings.foundry_project_endpoint, "OPENINSURE_FOUNDRY_PROJECT_ENDPOINT must be set"
        import httpx
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        response = httpx.get(
            f"{settings.foundry_project_endpoint.rstrip('/')}/openai/deployments?api-version=2024-10-21",
            headers={"Authorization": f"Bearer {token.token}"},
            timeout=10,
        )
        assert response.status_code == 200
