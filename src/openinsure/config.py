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
    sql_connection_string: str = ""  # SENSITIVE — use Container App secrets (secretRef) in production
    sql_database_name: str = "openinsure"

    # Azure Cosmos DB (NoSQL API)
    cosmos_endpoint: str = ""
    cosmos_database_name: str = "openinsure-knowledge"
    cosmos_graph_name: str = "insurance-graph"
    cosmos_key: str = ""  # SENSITIVE — use Container App secrets (secretRef) in production

    # Azure AI Search
    search_endpoint: str = ""
    search_index_name: str = "openinsure-knowledge"
    search_connection_id: str = ""  # Foundry project connection ID for AI Search
    search_admin_key: str = ""  # SENSITIVE — use Container App secrets (secretRef) in production

    # Azure Blob Storage
    storage_account_url: str = ""
    storage_container_name: str = "documents"

    # Azure Event Grid / Service Bus
    eventgrid_endpoint: str = ""
    servicebus_connection_string: str = ""  # SENSITIVE — use Container App secrets (secretRef) in production
    servicebus_queue_name: str = "openinsure-events"

    # Azure AI / Foundry
    foundry_project_endpoint: str = ""
    foundry_model_deployment: str = "gpt-5.2"

    # Azure AI Document Intelligence
    document_intelligence_endpoint: str = ""

    # CORS
    cors_origins: str = ""

    # Authentication
    api_key: str = ""  # SENSITIVE — use Container App secrets (secretRef) in production
    require_auth: bool = False
    # "production" = full JWKS validation; set to "dev" explicitly for local dev only
    jwt_validation_mode: str = "production"
    jwt_issuer: str = ""  # Expected issuer (iss) claim, e.g. https://login.microsoftonline.com/{tenant}/v2.0
    jwt_audience: str = ""  # Expected audience (aud) claim, e.g. api://<client-id>

    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_auth_per_minute: int = 10
    rate_limit_foundry_per_minute: int = 20

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
