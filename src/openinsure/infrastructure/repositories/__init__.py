"""OpenInsure repository implementations.

Each module exposes an in-memory repository (for local dev / tests) and,
eventually, a SQL-backed repository for Azure SQL.
"""

from openinsure.infrastructure.repositories.claims import InMemoryClaimRepository
from openinsure.infrastructure.repositories.policies import InMemoryPolicyRepository
from openinsure.infrastructure.repositories.products import InMemoryProductRepository
from openinsure.infrastructure.repositories.submissions import InMemorySubmissionRepository

__all__ = [
    "InMemoryClaimRepository",
    "InMemoryPolicyRepository",
    "InMemoryProductRepository",
    "InMemorySubmissionRepository",
]
