"""OpenInsure services layer.

Re-exports all service classes for convenient access::

    from openinsure.services import CyberRatingEngine, PolicyLifecycleService
"""

from openinsure.services.claims_processing import ClaimsProcessingService
from openinsure.services.claims_service import ClaimsService
from openinsure.services.document_processing import DocumentProcessingService
from openinsure.services.event_publisher import get_recent_events, publish_domain_event
from openinsure.services.policy_lifecycle import PolicyLifecycleService
from openinsure.services.rating import CyberRatingEngine
from openinsure.services.submission_service import SubmissionService

__all__ = [
    "ClaimsProcessingService",
    "ClaimsService",
    "CyberRatingEngine",
    "DocumentProcessingService",
    "PolicyLifecycleService",
    "SubmissionService",
    "get_recent_events",
    "publish_domain_event",
]
