"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OpenInsure application settings.

    All settings loaded from environment variables with OPENINSURE_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="OPENINSURE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "OpenInsure"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Azure SQL Database
    sql_connection_string: str = ""
    sql_database_name: str = "openinsure"

    # Azure Cosmos DB (Gremlin API)
    cosmos_endpoint: str = ""
    cosmos_database_name: str = "openinsure-knowledge"
    cosmos_graph_name: str = "insurance-graph"

    # Azure AI Search
    search_endpoint: str = ""
    search_index_name: str = "openinsure-knowledge"

    # Azure Blob Storage
    storage_account_url: str = ""
    storage_container_name: str = "documents"

    # Azure Event Grid / Service Bus
    eventgrid_endpoint: str = ""
    servicebus_connection_string: str = ""
    servicebus_queue_name: str = "openinsure-events"

    # Azure AI / Foundry
    foundry_project_endpoint: str = ""
    foundry_model_deployment: str = "gpt-5.2"

    # CORS
    cors_origins: str = ""

    # Authentication
    api_key: str = ""
    require_auth: bool = False

    # Deployment
    deployment_type: str = "mga"  # "carrier" or "mga"

    # Test/Storage mode
    storage_mode: str = "memory"  # "memory" for local dev, "azure" for real Azure resources

    # Server
    host: str = "0.0.0.0"  # nosec B104 — bind-all is intentional for container deployment
    port: int = 8000
    workers: int = 4


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
