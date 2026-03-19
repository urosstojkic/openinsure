"""Service factory — instantiates real or mock adapters based on config.

When storage_mode="memory": InMemory repositories, no Azure connections
When storage_mode="azure": SQL repositories, real Azure adapters
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from openinsure.config import get_settings

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter
    from openinsure.infrastructure.repository import BaseRepository


@lru_cache
def get_database_adapter() -> DatabaseAdapter | None:
    """Return a shared DatabaseAdapter, or ``None`` when not configured."""
    settings = get_settings()
    if not settings.sql_connection_string:
        return None
    from openinsure.infrastructure.database import DatabaseAdapter

    return DatabaseAdapter(settings.sql_connection_string, settings.sql_database_name)


# -- domain repositories ---------------------------------------------------


@lru_cache
def get_submission_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_submissions import SqlSubmissionRepository

        db = get_database_adapter()
        return SqlSubmissionRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.submissions import InMemorySubmissionRepository

    return InMemorySubmissionRepository()


@lru_cache
def get_policy_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_policies import SqlPolicyRepository

        db = get_database_adapter()
        return SqlPolicyRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.policies import InMemoryPolicyRepository

    return InMemoryPolicyRepository()


@lru_cache
def get_claim_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_claims import SqlClaimRepository

        db = get_database_adapter()
        return SqlClaimRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.claims import InMemoryClaimRepository

    return InMemoryClaimRepository()


@lru_cache
def get_product_repository() -> BaseRepository:
    # Products use in-memory for now; SQL variant can be added later
    from openinsure.infrastructure.repositories.products import InMemoryProductRepository

    return InMemoryProductRepository()


@lru_cache
def get_billing_repository() -> BaseRepository:
    # Billing uses in-memory for now; SQL variant can be added later
    from openinsure.infrastructure.repositories.billing import InMemoryBillingRepository

    return InMemoryBillingRepository()


@lru_cache
def get_event_bus():
    """Return a shared EventBusAdapter, or ``None`` when not configured."""
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.eventgrid_endpoint:
        from openinsure.infrastructure.event_bus import EventBusAdapter

        return EventBusAdapter(
            event_grid_endpoint=settings.eventgrid_endpoint,
            service_bus_namespace=settings.servicebus_connection_string,
        )
    return None


@lru_cache
def get_blob_storage():
    """Return a shared BlobStorageAdapter, or ``None`` when not configured."""
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.storage_account_url:
        from openinsure.infrastructure.blob_storage import BlobStorageAdapter

        return BlobStorageAdapter(settings.storage_account_url, settings.storage_container_name)
    return None


@lru_cache
def get_knowledge_store():
    """Return a CosmosKnowledgeStore, or ``None`` when Cosmos DB is not configured."""
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.cosmos_endpoint:
        from openinsure.infrastructure.cosmos_nosql import CosmosKnowledgeStore

        return CosmosKnowledgeStore(
            settings.cosmos_endpoint,
            settings.cosmos_database_name,
            settings.cosmos_graph_name,
        )
    return None  # Fall back to static dicts in KnowledgeAgent


@lru_cache
def get_compliance_repository():
    """Return decision/audit repositories for the compliance module."""
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_compliance import SqlComplianceRepository

        db = get_database_adapter()
        return SqlComplianceRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.compliance import InMemoryComplianceRepository

    return InMemoryComplianceRepository()


@lru_cache
def get_reinsurance_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_reinsurance import SqlReinsuranceRepository

        db = get_database_adapter()
        return SqlReinsuranceRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.reinsurance import InMemoryReinsuranceRepository

    return InMemoryReinsuranceRepository()


@lru_cache
def get_cession_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_reinsurance import SqlCessionRepository

        db = get_database_adapter()
        return SqlCessionRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.reinsurance_sub import InMemoryCessionRepository

    return InMemoryCessionRepository()


@lru_cache
def get_recovery_repository() -> BaseRepository:
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.sql_connection_string:
        from openinsure.infrastructure.repositories.sql_reinsurance import SqlRecoveryRepository

        db = get_database_adapter()
        return SqlRecoveryRepository(db)  # type: ignore[arg-type]
    from openinsure.infrastructure.repositories.reinsurance_sub import InMemoryRecoveryRepository

    return InMemoryRecoveryRepository()


@lru_cache
def get_search_adapter():
    """Return a shared SearchAdapter, or ``None`` when not configured."""
    settings = get_settings()
    if settings.storage_mode == "azure" and settings.search_endpoint:
        from openinsure.infrastructure.ai_search import SearchAdapter

        return SearchAdapter(settings.search_endpoint, settings.search_index_name)
    return None
