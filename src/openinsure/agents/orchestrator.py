"""Multi-agent orchestrator for OpenInsure.

Coordinates multi-step insurance workflows by sequencing calls to
specialised agents, collecting all DecisionRecords, and producing a
unified workflow result with a full audit trail.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from openinsure.agents.base import DecisionRecord
from openinsure.agents.claims_agent import ClaimsAgent
from openinsure.agents.compliance_agent import ComplianceAgent
from openinsure.agents.document_agent import DocumentAgent
from openinsure.agents.knowledge_agent import KnowledgeAgent
from openinsure.agents.policy_agent import PolicyAgent
from openinsure.agents.submission_agent import SubmissionAgent
from openinsure.agents.underwriting_agent import UnderwritingAgent
from openinsure.services.event_publisher import publish_domain_event

logger = structlog.get_logger()


class WorkflowResult:
    """Container for the output of a multi-agent workflow."""

    def __init__(self, workflow_id: str, workflow_type: str):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.started_at = datetime.now(UTC)
        self.completed_at: datetime | None = None
        self.steps: list[dict[str, Any]] = []
        self.decision_records: list[DecisionRecord] = []
        self.final_result: dict[str, Any] = {}
        self.success: bool = False
        self.error: str | None = None

    def add_step(
        self,
        step_name: str,
        agent_id: str,
        result: dict[str, Any],
        decision: DecisionRecord,
    ) -> None:
        self.steps.append(
            {
                "step_name": step_name,
                "agent_id": agent_id,
                "success": "error" not in result,
                "escalation_required": result.get("escalation_required", False),
                "confidence": decision.confidence,
                "execution_time_ms": decision.execution_time_ms,
            }
        )
        self.decision_records.append(decision)

    def complete(self, result: dict[str, Any], *, success: bool = True) -> None:
        self.completed_at = datetime.now(UTC)
        self.final_result = result
        self.success = success

    def fail(self, error: str) -> None:
        self.completed_at = datetime.now(UTC)
        self.error = error
        self.success = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "started_at": self.started_at.isoformat(),
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "success": self.success,
            "error": self.error,
            "steps": self.steps,
            "decision_record_count": len(self.decision_records),
            "final_result": self.final_result,
        }


class Orchestrator:
    """Coordinates multi-agent insurance workflows.

    Supported workflows:
    - :meth:`new_business_workflow` – Submission → Document → Underwriting
      → Policy → Compliance
    - :meth:`claims_workflow` – FNOL → Coverage Check → Reserve → Triage
      → Investigation
    """

    def __init__(
        self,
        *,
        submission_agent: SubmissionAgent | None = None,
        document_agent: DocumentAgent | None = None,
        underwriting_agent: UnderwritingAgent | None = None,
        policy_agent: PolicyAgent | None = None,
        claims_agent: ClaimsAgent | None = None,
        knowledge_agent: KnowledgeAgent | None = None,
        compliance_agent: ComplianceAgent | None = None,
    ):
        self.submission_agent = submission_agent or SubmissionAgent()
        self.document_agent = document_agent or DocumentAgent()
        self.underwriting_agent = underwriting_agent or UnderwritingAgent()
        self.policy_agent = policy_agent or PolicyAgent()
        self.claims_agent = claims_agent or ClaimsAgent()
        self.knowledge_agent = knowledge_agent or KnowledgeAgent()
        self.compliance_agent = compliance_agent or ComplianceAgent()
        self.logger = structlog.get_logger().bind(component="orchestrator")

    # ------------------------------------------------------------------
    # New business workflow
    # ------------------------------------------------------------------

    async def new_business_workflow(self, submission: dict[str, Any]) -> WorkflowResult:
        """Execute the full new-business pipeline.

        Steps:
        1. Submission intake & triage
        2. Document processing (classify + extract)
        3. Knowledge retrieval (UW guidelines)
        4. Underwriting & pricing
        5. Policy binding
        6. Compliance check on all decisions
        """
        workflow = WorkflowResult(
            workflow_id=str(uuid4()),
            workflow_type="new_business",
        )
        self.logger.info(
            "workflow.new_business.start",
            workflow_id=workflow.workflow_id,
        )

        try:
            # --- Step 1: Submission intake & triage ---
            sub_result, sub_decision = await self.submission_agent.execute(
                {"type": "submission_intake", "submission": submission}
            )
            workflow.add_step("submission_intake", "submission_agent", sub_result, sub_decision)
            await publish_domain_event(
                event_type="workflow.submission_intake_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "submission_intake", "workflow_id": workflow.workflow_id},
            )

            if sub_result.get("escalation_required"):
                self.logger.warning("workflow.new_business.escalation", step="submission")

            triage = sub_result.get("triage_result", {})
            if not triage.get("appetite_match", True):
                workflow.complete(
                    {"status": "declined", "reason": triage.get("decline_reason")},
                    success=True,
                )
                return workflow

            # --- Step 2: Document processing ---
            documents = submission.get("documents", [])
            for doc in documents:
                doc_result, doc_decision = await self.document_agent.execute(
                    {"type": "classify", "document": doc}
                )
                workflow.add_step("document_classify", "document_agent", doc_result, doc_decision)

                ext_result, ext_decision = await self.document_agent.execute(
                    {
                        "type": "extract",
                        "document": doc,
                        "document_type": doc_result.get("document_type"),
                    }
                )
                workflow.add_step("document_extract", "document_agent", ext_result, ext_decision)

            # --- Step 3: Knowledge retrieval ---
            lob = submission.get("line_of_business", "cyber")
            kg_result, kg_decision = await self.knowledge_agent.execute(
                {"type": "get_guidelines", "line_of_business": lob}
            )
            workflow.add_step("knowledge_retrieval", "knowledge_agent", kg_result, kg_decision)
            await publish_domain_event(
                event_type="workflow.knowledge_retrieval_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "knowledge_retrieval", "workflow_id": workflow.workflow_id},
            )

            # --- Step 4: Underwriting & pricing ---
            extracted = sub_result.get("extracted_data", {})
            uw_result, uw_decision = await self.underwriting_agent.execute(
                {
                    "type": "underwrite",
                    "extracted_data": extracted,
                    "line_of_business": lob,
                    "triage_result": triage,
                }
            )
            workflow.add_step("underwriting", "underwriting_agent", uw_result, uw_decision)
            await publish_domain_event(
                event_type="workflow.underwriting_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "underwriting", "workflow_id": workflow.workflow_id},
            )

            if uw_result.get("escalation_required"):
                self.logger.warning("workflow.new_business.escalation", step="underwriting")

            # --- Step 5: Policy binding ---
            quote = uw_result.get("quote", {})
            bind_result, bind_decision = await self.policy_agent.execute(
                {
                    "type": "bind",
                    "quote": quote,
                    "submission": {
                        **submission,
                        "submission_id": str(uuid4()),
                    },
                }
            )
            workflow.add_step("policy_bind", "policy_agent", bind_result, bind_decision)
            await publish_domain_event(
                event_type="workflow.policy_bind_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "policy_bind", "workflow_id": workflow.workflow_id},
            )

            # --- Step 6: Compliance check ---
            comp_result, comp_decision = await self.compliance_agent.execute(
                {
                    "type": "check_compliance",
                    "decision_records": [dr.model_dump(mode="json") for dr in workflow.decision_records],
                }
            )
            workflow.add_step("compliance_check", "compliance_agent", comp_result, comp_decision)
            await publish_domain_event(
                event_type="workflow.compliance_check_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "compliance_check", "workflow_id": workflow.workflow_id},
            )

            workflow.complete(
                {
                    "status": "bound" if bind_result.get("success") else "failed",
                    "policy": bind_result.get("policy"),
                    "quote": quote,
                    "triage": triage,
                    "compliance": comp_result.get("findings"),
                }
            )

        except Exception as e:
            self.logger.exception("workflow.new_business.error", error=str(e))
            workflow.fail(str(e))

        self.logger.info(
            "workflow.new_business.complete",
            workflow_id=workflow.workflow_id,
            success=workflow.success,
            steps=len(workflow.steps),
        )
        return workflow

    # ------------------------------------------------------------------
    # Claims workflow
    # ------------------------------------------------------------------

    async def claims_workflow(self, claim_report: dict[str, Any], policy: dict[str, Any]) -> WorkflowResult:
        """Execute the claims processing pipeline.

        Steps:
        1. FNOL intake
        2. Coverage verification
        3. Reserve setting
        4. Claim triage
        5. Compliance check on all decisions
        """
        workflow = WorkflowResult(
            workflow_id=str(uuid4()),
            workflow_type="claims",
        )
        self.logger.info(
            "workflow.claims.start",
            workflow_id=workflow.workflow_id,
        )

        try:
            # --- Step 1-4: Full FNOL pipeline (handled atomically by ClaimsAgent) ---
            claims_result, claims_decision = await self.claims_agent.execute(
                {
                    "type": "fnol",
                    "claim_report": claim_report,
                    "policy": policy,
                }
            )
            workflow.add_step("claims_pipeline", "claims_agent", claims_result, claims_decision)
            await publish_domain_event(
                event_type="workflow.claims_pipeline_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "claims_pipeline", "workflow_id": workflow.workflow_id},
            )

            if claims_result.get("escalation_required"):
                self.logger.warning("workflow.claims.escalation", step="claims_pipeline")

            # --- Step 5: Investigation support (if required) ---
            triage = claims_result.get("triage_result", {})
            if triage.get("requires_investigation"):
                fnol = claims_result.get("fnol", {})
                inv_result, inv_decision = await self.claims_agent.execute(
                    {
                        "type": "investigation",
                        "claim_id": fnol.get("claim_number"),
                    }
                )
                workflow.add_step("investigation_support", "claims_agent", inv_result, inv_decision)

            # --- Step 6: Compliance check ---
            comp_result, comp_decision = await self.compliance_agent.execute(
                {
                    "type": "check_compliance",
                    "decision_records": [dr.model_dump(mode="json") for dr in workflow.decision_records],
                }
            )
            workflow.add_step("compliance_check", "compliance_agent", comp_result, comp_decision)
            await publish_domain_event(
                event_type="workflow.claims_compliance_complete",
                subject=f"/workflows/{workflow.workflow_id}",
                data={"step": "compliance_check", "workflow_id": workflow.workflow_id},
            )

            workflow.complete(
                {
                    "status": "triaged",
                    "fnol": claims_result.get("fnol"),
                    "coverage": claims_result.get("coverage_result"),
                    "reserves": claims_result.get("reserves"),
                    "triage": triage,
                    "compliance": comp_result.get("findings"),
                }
            )

        except Exception as e:
            self.logger.exception("workflow.claims.error", error=str(e))
            workflow.fail(str(e))

        self.logger.info(
            "workflow.claims.complete",
            workflow_id=workflow.workflow_id,
            success=workflow.success,
            steps=len(workflow.steps),
        )
        return workflow
