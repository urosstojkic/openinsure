"""Compliance and audit agent for OpenInsure.

Performs regulatory compliance checking, audit trail generation,
bias monitoring across outcomes, and EU AI Act documentation generation.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog

from openinsure.agents.base import (
    AgentCapability,
    AgentConfig,
    DecisionRecord,
    InsuranceAgent,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Compliance rule sets
# ---------------------------------------------------------------------------

COMPLIANCE_RULES: dict[str, list[dict[str, Any]]] = {
    "eu_ai_act": [
        {
            "rule_id": "AIA-12",
            "article": "Art. 12",
            "name": "Record-Keeping",
            "check": "decision_record_present",
            "description": "Every AI decision must produce a decision record",
        },
        {
            "rule_id": "AIA-13",
            "article": "Art. 13",
            "name": "Transparency",
            "check": "reasoning_documented",
            "description": "AI reasoning must be documented and explainable",
        },
        {
            "rule_id": "AIA-14",
            "article": "Art. 14",
            "name": "Human Oversight",
            "check": "human_oversight_defined",
            "description": "Human oversight mechanism must be defined",
        },
        {
            "rule_id": "AIA-10",
            "article": "Art. 10",
            "name": "Data Governance",
            "check": "data_sources_documented",
            "description": "Data sources used must be documented",
        },
        {
            "rule_id": "AIA-15",
            "article": "Art. 15",
            "name": "Accuracy & Robustness",
            "check": "confidence_reported",
            "description": "Confidence/accuracy metrics must be reported",
        },
    ],
    "insurance_regulatory": [
        {
            "rule_id": "INS-UW-01",
            "name": "Underwriting Documentation",
            "check": "underwriting_rationale_present",
            "description": "All underwriting decisions must include a documented rationale",
        },
        {
            "rule_id": "INS-CLM-01",
            "name": "Claims Handling",
            "check": "claims_timeline_met",
            "description": "Claims must be acknowledged within regulatory timeframes",
        },
        {
            "rule_id": "INS-FAIR-01",
            "name": "Fair Dealing",
            "check": "no_unfair_discrimination",
            "description": "Decisions must not unfairly discriminate on protected characteristics",
        },
    ],
}

BIAS_DIMENSIONS = [
    "industry",
    "company_size",
    "geography",
    "revenue_band",
]


class ComplianceAgent(InsuranceAgent):
    """Compliance checking, audit, and bias monitoring agent.

    Supported task types dispatched by :meth:`process`:
    - ``check_compliance`` – validate decisions against regulatory rules.
    - ``generate_audit_report`` – build an audit trail from decision records.
    - ``check_bias`` – monitor for bias across decision outcomes.
    - ``generate_eu_ai_act_documentation`` – produce EU AI Act documentation.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="compliance_agent",
                agent_version="0.1.0",
                authority_limit=Decimal("0"),
            )
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="check_compliance",
                description="Check decision records for regulatory compliance",
                required_inputs=["decision_records"],
                produces=["compliance_result"],
            ),
            AgentCapability(
                name="generate_audit_report",
                description="Generate an audit trail report from decision records",
                required_inputs=["decision_records"],
                produces=["audit_report"],
            ),
            AgentCapability(
                name="check_bias",
                description="Monitor for bias across AI decision outcomes",
                required_inputs=["decision_records"],
                produces=["bias_report"],
            ),
            AgentCapability(
                name="generate_eu_ai_act_documentation",
                description="Generate EU AI Act compliance documentation",
                required_inputs=["decision_records", "system_info"],
                produces=["eu_ai_act_documentation"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = task.get("type", "check_compliance")
        handler = {
            "check_compliance": self._check_compliance,
            "generate_audit_report": self._generate_audit_report,
            "check_bias": self._check_bias,
            "generate_eu_ai_act_documentation": self._generate_eu_ai_act_docs,
        }.get(task_type)

        if handler is None:
            raise ValueError(f"Unknown compliance task type: {task_type}")

        self.logger.info("compliance.task.dispatch", task_type=task_type)
        return await handler(task)

    # ------------------------------------------------------------------
    # Compliance checking
    # ------------------------------------------------------------------

    async def _check_compliance(self, task: dict[str, Any]) -> dict[str, Any]:
        """Validate decision records against regulatory rule sets."""
        records = self._load_records(task)
        rule_sets = task.get("rule_sets", ["eu_ai_act", "insurance_regulatory"])

        all_findings: list[dict[str, Any]] = []
        for rs_name in rule_sets:
            rules = COMPLIANCE_RULES.get(rs_name, [])
            for rule in rules:
                for record in records:
                    finding = self._evaluate_rule(rule, record)
                    if finding:
                        all_findings.append(finding)

        compliant = all(f["status"] == "pass" for f in all_findings) if all_findings else False
        pass_count = sum(1 for f in all_findings if f["status"] == "pass")
        fail_count = sum(1 for f in all_findings if f["status"] == "fail")

        self.logger.info(
            "compliance.checked",
            findings=len(all_findings),
            pass_count=pass_count,
            fail_count=fail_count,
        )

        return {
            "compliant": compliant,
            "findings": all_findings,
            "summary": {
                "total_checks": len(all_findings),
                "passed": pass_count,
                "failed": fail_count,
                "rule_sets_evaluated": rule_sets,
            },
            "confidence": 0.95,
            "reasoning": {
                "step": "check_compliance",
                "rule_sets": rule_sets,
                "records_checked": len(records),
            },
            "data_sources": ["decision_records", "compliance_rules"],
            "knowledge_queries": [f"compliance_rules/{rs}" for rs in rule_sets],
        }

    def _evaluate_rule(self, rule: dict[str, Any], record: dict[str, Any]) -> dict[str, Any] | None:
        """Evaluate a single compliance rule against a decision record."""
        check = rule.get("check", "")
        status = "pass"
        detail = ""

        if check == "decision_record_present":
            if not record.get("decision_id"):
                status = "fail"
                detail = "Missing decision_id"

        elif check == "reasoning_documented":
            reasoning = record.get("reasoning", {})
            if not reasoning:
                status = "fail"
                detail = "No reasoning documented"

        elif check == "human_oversight_defined":
            oversight = record.get("human_oversight", {})
            if not oversight or "required" not in oversight:
                status = "fail"
                detail = "Human oversight not defined"

        elif check == "data_sources_documented":
            sources = record.get("data_sources_used", [])
            if not sources:
                status = "fail"
                detail = "No data sources documented"

        elif check == "confidence_reported":
            confidence = record.get("confidence")
            if confidence is None:
                status = "fail"
                detail = "Confidence not reported"

        elif check == "underwriting_rationale_present":
            if "underwriting" in record.get("decision_type", ""):
                reasoning = record.get("reasoning", {})
                if not reasoning:
                    status = "fail"
                    detail = "Underwriting rationale missing"

        elif check == "claims_timeline_met":
            # Stub: always passes unless execution took > 24h
            if record.get("execution_time_ms", 0) > 86_400_000:
                status = "fail"
                detail = "Claims processing exceeded 24-hour SLA"

        elif check == "no_unfair_discrimination":
            fairness = record.get("fairness_metrics", {})
            if fairness.get("disparate_impact_detected"):
                status = "fail"
                detail = "Potential unfair discrimination detected"

        return {
            "rule_id": rule.get("rule_id"),
            "rule_name": rule.get("name"),
            "article": rule.get("article", ""),
            "status": status,
            "detail": detail,
            "decision_id": str(record.get("decision_id", "")),
            "agent_id": record.get("agent_id", ""),
        }

    # ------------------------------------------------------------------
    # Audit report
    # ------------------------------------------------------------------

    async def _generate_audit_report(self, task: dict[str, Any]) -> dict[str, Any]:
        """Generate a structured audit trail from decision records."""
        records = self._load_records(task)
        now = datetime.now(UTC)

        entries: list[dict[str, Any]] = []
        for record in records:
            entries.append(
                {
                    "decision_id": str(record.get("decision_id", "")),
                    "timestamp": record.get("timestamp", ""),
                    "agent_id": record.get("agent_id", ""),
                    "decision_type": record.get("decision_type", ""),
                    "confidence": record.get("confidence", 0.0),
                    "human_oversight_required": record.get("human_oversight", {}).get("required", False),
                    "error": record.get("error"),
                    "execution_time_ms": record.get("execution_time_ms", 0),
                    "data_sources": record.get("data_sources_used", []),
                }
            )

        report = {
            "report_id": str(uuid4()),
            "generated_at": now.isoformat(),
            "record_count": len(entries),
            "entries": entries,
            "summary": {
                "total_decisions": len(entries),
                "errors": sum(1 for e in entries if e.get("error")),
                "escalations": sum(1 for e in entries if e.get("human_oversight_required")),
                "avg_confidence": (
                    round(
                        sum(e.get("confidence", 0.0) for e in entries) / len(entries),
                        4,
                    )
                    if entries
                    else 0.0
                ),
                "avg_execution_ms": (
                    round(
                        sum(e.get("execution_time_ms", 0) for e in entries) / len(entries),
                        2,
                    )
                    if entries
                    else 0.0
                ),
            },
        }

        self.logger.info(
            "compliance.audit.generated",
            records=len(entries),
        )

        return {
            "audit_report": report,
            "confidence": 0.95,
            "reasoning": {"step": "generate_audit_report", "records": len(entries)},
            "data_sources": ["decision_records"],
            "knowledge_queries": ["audit_requirements"],
        }

    # ------------------------------------------------------------------
    # Bias monitoring
    # ------------------------------------------------------------------

    async def _check_bias(self, task: dict[str, Any]) -> dict[str, Any]:
        """Monitor for bias across AI decision outcomes."""
        records = self._load_records(task)
        dimensions = task.get("dimensions", BIAS_DIMENSIONS)

        dimension_reports: list[dict[str, Any]] = []
        alerts: list[str] = []

        for dim in dimensions:
            report = self._analyze_dimension(records, dim)
            dimension_reports.append(report)
            if report.get("alert"):
                alerts.append(report["alert"])

        self.logger.info(
            "compliance.bias.checked",
            dimensions=len(dimensions),
            alerts=len(alerts),
        )

        return {
            "bias_report": {
                "dimensions_analyzed": dimensions,
                "dimension_reports": dimension_reports,
                "alerts": alerts,
                "overall_status": "alert" if alerts else "ok",
            },
            "confidence": 0.80,
            "reasoning": {
                "step": "check_bias",
                "dimensions": dimensions,
                "records_analyzed": len(records),
            },
            "data_sources": ["decision_records"],
            "knowledge_queries": ["fairness_thresholds", "bias_detection"],
        }

    @staticmethod
    def _analyze_dimension(records: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
        """Analyze a single dimension for bias signals."""
        # Group records by dimension value
        groups: dict[str, list[float]] = {}
        for rec in records:
            key = str(rec.get("input_summary", {}).get(dimension, "unknown"))
            groups.setdefault(key, []).append(rec.get("confidence", 0.0))

        if len(groups) < 2:
            return {
                "dimension": dimension,
                "group_count": len(groups),
                "alert": None,
                "detail": "Insufficient groups for comparison",
            }

        # Compute per-group average confidence
        averages = {k: round(sum(v) / len(v), 4) if v else 0.0 for k, v in groups.items()}
        values = list(averages.values())
        spread = round(max(values) - min(values), 4) if values else 0.0

        alert = None
        if spread > 0.2:
            alert = f"Dimension '{dimension}' shows confidence spread of {spread} across groups: {averages}"

        return {
            "dimension": dimension,
            "group_count": len(groups),
            "group_averages": averages,
            "spread": spread,
            "alert": alert,
        }

    # ------------------------------------------------------------------
    # EU AI Act documentation
    # ------------------------------------------------------------------

    async def _generate_eu_ai_act_docs(self, task: dict[str, Any]) -> dict[str, Any]:
        """Generate EU AI Act compliance documentation package."""
        records = self._load_records(task)
        system_info = task.get("system_info", {})
        now = datetime.now(UTC)

        # Run compliance check internally
        compliance_result = await self._check_compliance({"decision_records": records, "rule_sets": ["eu_ai_act"]})

        documentation = {
            "document_id": str(uuid4()),
            "generated_at": now.isoformat(),
            "system_description": {
                "name": system_info.get("name", "OpenInsure AI Agent Platform"),
                "version": system_info.get("version", "0.1.0"),
                "purpose": system_info.get(
                    "purpose",
                    "Automated insurance underwriting, claims processing, and policy management",
                ),
                "risk_classification": "high",
                "intended_users": [
                    "insurance underwriters",
                    "claims adjusters",
                    "compliance officers",
                ],
            },
            "article_12_record_keeping": {
                "decision_record_schema": "DecisionRecord",
                "storage": "Azure SQL Database",
                "retention_period": "10 years",
                "total_records_audited": len(records),
            },
            "article_13_transparency": {
                "reasoning_mechanism": "Structured reasoning dict per decision",
                "explainability": "All decisions include reasoning, data sources, and confidence scores",
                "user_notification": "Decision records are surfaced via audit API",
            },
            "article_14_human_oversight": {
                "escalation_mechanism": "Confidence threshold + authority limits",
                "override_capability": True,
                "approval_workflow": "Decisions below threshold require human approval",
            },
            "article_15_accuracy": {
                "confidence_tracking": True,
                "monitoring": "Continuous bias and accuracy monitoring via ComplianceAgent",
            },
            "compliance_check_results": compliance_result.get("findings", []),
        }

        self.logger.info("compliance.eu_ai_act.generated")

        return {
            "eu_ai_act_documentation": documentation,
            "confidence": 0.90,
            "reasoning": {
                "step": "generate_eu_ai_act_documentation",
                "articles_covered": ["Art. 12", "Art. 13", "Art. 14", "Art. 15"],
            },
            "data_sources": ["decision_records", "system_info"],
            "knowledge_queries": ["eu_ai_act_requirements"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_records(task: dict[str, Any]) -> list[dict[str, Any]]:
        """Load decision records from task payload.

        Accepts either raw dicts or :class:`DecisionRecord` instances.
        """
        raw = task.get("decision_records", [])
        records: list[dict[str, Any]] = []
        for r in raw:
            if isinstance(r, DecisionRecord):
                records.append(r.model_dump(mode="json"))
            elif isinstance(r, dict):
                records.append(r)
        return records
