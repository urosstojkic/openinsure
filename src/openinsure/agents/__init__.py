"""OpenInsure AI Agent framework.

All agent classes are exported from this package for convenient
top-level imports::

    from openinsure.agents import SubmissionAgent, UnderwritingAgent
"""

from openinsure.agents.base import (
    AgentCapability,
    AgentConfig,
    DecisionRecord,
    InsuranceAgent,
)
from openinsure.agents.claims_agent import ClaimsAgent
from openinsure.agents.compliance_agent import ComplianceAgent
from openinsure.agents.document_agent import DocumentAgent
from openinsure.agents.knowledge_agent import KnowledgeAgent
from openinsure.agents.orchestrator import Orchestrator, WorkflowResult
from openinsure.agents.policy_agent import PolicyAgent
from openinsure.agents.prompts import (
    build_claims_assessment_prompt,
    build_compliance_audit_prompt,
    build_orchestration_prompt,
    build_policy_review_prompt,
    build_prompt_for_step,
    build_triage_prompt,
    build_underwriting_prompt,
)
from openinsure.agents.submission_agent import SubmissionAgent
from openinsure.agents.underwriting_agent import UnderwritingAgent

__all__ = [
    "AgentCapability",
    "AgentConfig",
    "ClaimsAgent",
    "ComplianceAgent",
    "DecisionRecord",
    "DocumentAgent",
    "InsuranceAgent",
    "KnowledgeAgent",
    "Orchestrator",
    "PolicyAgent",
    "SubmissionAgent",
    "UnderwritingAgent",
    "WorkflowResult",
    "build_claims_assessment_prompt",
    "build_compliance_audit_prompt",
    "build_orchestration_prompt",
    "build_policy_review_prompt",
    "build_prompt_for_step",
    "build_triage_prompt",
    "build_underwriting_prompt",
]
