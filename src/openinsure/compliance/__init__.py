"""OpenInsure Compliance Layer — EU AI Act compliance-by-design.

Provides decision record keeping (Art. 12), immutable audit trails,
and bias monitoring with disparate impact detection.
"""

from openinsure.compliance.audit_trail import AuditEvent, AuditTrailStore
from openinsure.compliance.bias_monitor import BiasMetric, BiasMonitor, BiasReport
from openinsure.compliance.decision_record import DecisionRecordStore

__all__ = [
    "AuditEvent",
    "AuditTrailStore",
    "BiasMetric",
    "BiasMonitor",
    "BiasReport",
    "DecisionRecordStore",
]
