"""OpenInsure Compliance Layer — EU AI Act compliance-by-design.

Provides decision record keeping (Art. 12), immutable audit trails,
and bias monitoring with disparate impact detection.

Bias monitoring is consolidated in :mod:`openinsure.services.bias_monitor`
and re-exported here for convenience.
"""

from openinsure.compliance.audit_trail import AuditEvent, AuditTrailStore
from openinsure.compliance.decision_record import DecisionRecordStore
from openinsure.services.bias_monitor import BiasAnalysisResult, analyze_submission_bias, generate_bias_report

__all__ = [
    "AuditEvent",
    "AuditTrailStore",
    "BiasAnalysisResult",
    "DecisionRecordStore",
    "analyze_submission_bias",
    "generate_bias_report",
]
