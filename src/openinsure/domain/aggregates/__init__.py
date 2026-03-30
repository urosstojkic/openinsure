"""Aggregate roots for OpenInsure domain model.

Each aggregate root:
- Owns its state transitions (validates before mutating)
- Emits domain events on mutation
- Never directly modifies another aggregate
"""

from openinsure.domain.aggregates.claim import ClaimAggregate
from openinsure.domain.aggregates.policy import PolicyAggregate
from openinsure.domain.aggregates.submission import SubmissionAggregate

__all__ = [
    "ClaimAggregate",
    "PolicyAggregate",
    "SubmissionAggregate",
]
