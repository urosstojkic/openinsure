"""Submission intake and triage agent for OpenInsure.

Handles the first stage of the insurance pipeline: receiving submissions,
classifying attached documents, extracting structured data, validating
completeness against product requirements, and triaging the submission
(appetite matching, risk scoring, priority assignment).
"""

from decimal import Decimal
from typing import Any

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOCUMENT_TYPES = [
    "acord_application",
    "loss_run",
    "financial_statement",
    "supplemental",
    "sov",
    "prior_policy",
]

REQUIRED_FIELDS_BY_LOB: dict[str, list[str]] = {
    "cyber": [
        "applicant_name",
        "industry_sic_code",
        "annual_revenue",
        "employee_count",
        "has_mfa",
        "has_endpoint_protection",
        "has_backup_strategy",
        "has_incident_response_plan",
    ],
    "general_liability": [
        "applicant_name",
        "annual_revenue",
        "employee_count",
        "business_description",
        "prior_claims_count",
    ],
    "property": [
        "applicant_name",
        "total_insured_value",
        "construction_type",
        "year_built",
        "sprinkler_system",
    ],
}

APPETITE_RULES: dict[str, dict[str, Any]] = {
    "cyber": {
        "min_revenue": Decimal("1000000"),
        "max_revenue": Decimal("5000000000"),
        "excluded_sic_codes": ["6021", "6022"],  # Banks
        "max_prior_incidents": 5,
    },
    "general_liability": {
        "min_revenue": Decimal("500000"),
        "max_revenue": Decimal("2000000000"),
        "excluded_sic_codes": [],
    },
    "property": {
        "min_insured_value": Decimal("100000"),
        "max_insured_value": Decimal("500000000"),
    },
}


class SubmissionAgent(InsuranceAgent):
    """Submission intake, classification, extraction, and triage agent.

    Pipeline steps executed by :meth:`process`:
    1. **classify_documents** – identify document types attached to the
       submission.
    2. **extract_data** – pull structured fields from each document.
    3. **validate_completeness** – check extracted data against product
       requirements for the requested line of business.
    4. **triage** – appetite matching, risk scoring, priority assignment.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="submission_agent",
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
                name="intake",
                description="Receive and register a new insurance submission",
                required_inputs=["submission"],
                produces=["submission_id", "status"],
            ),
            AgentCapability(
                name="classify_documents",
                description="Classify attached documents by type",
                required_inputs=["documents"],
                produces=["classified_documents"],
            ),
            AgentCapability(
                name="extract_data",
                description="Extract structured data from submission documents",
                required_inputs=["classified_documents"],
                produces=["extracted_data"],
            ),
            AgentCapability(
                name="validate_completeness",
                description="Validate extracted data against product requirements",
                required_inputs=["extracted_data", "line_of_business"],
                produces=["validation_result", "missing_fields"],
            ),
            AgentCapability(
                name="triage",
                description="Score, prioritize, and route the submission",
                required_inputs=["extracted_data", "line_of_business"],
                produces=["triage_result"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run the full submission intake pipeline.

        Expected *task* keys:
        - ``type``: ``"submission_intake"``
        - ``submission``: dict with at least ``line_of_business`` and
          ``documents``.
        """
        submission = task.get("submission", {})
        lob = submission.get("line_of_business", "cyber")
        documents = submission.get("documents", [])

        self.logger.info(
            "submission.pipeline.start",
            lob=lob,
            document_count=len(documents),
        )

        # Step 1 – Document classification
        classified = await self._classify_documents(documents)

        # Step 2 – Data extraction
        extracted = await self._extract_data(classified, lob)

        # Step 3 – Completeness validation
        validation = await self._validate_completeness(extracted, lob)

        # Step 4 – Triage
        triage = await self._triage(extracted, lob)

        confidence = self._overall_confidence(classified, validation, triage)

        return {
            "classified_documents": classified,
            "extracted_data": extracted,
            "validation_result": validation,
            "triage_result": triage,
            "confidence": confidence,
            "reasoning": {
                "steps": [
                    "document_classification",
                    "data_extraction",
                    "completeness_validation",
                    "triage",
                ],
                "lob": lob,
                "document_count": len(documents),
            },
            "data_sources": ["submission_documents", "product_definitions"],
            "knowledge_queries": [
                f"appetite_rules/{lob}",
                f"required_fields/{lob}",
            ],
        }

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    async def _classify_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Classify each document by type.

        In production this calls the Document AI model; here we use
        heuristic classification based on filename and metadata.
        """
        classified: list[dict[str, Any]] = []
        for doc in documents:
            filename = doc.get("filename", "").lower()
            doc_type = self._heuristic_classify(filename)
            classified.append(
                {
                    **doc,
                    "classified_type": doc_type,
                    "classification_confidence": (0.95 if doc_type != "unknown" else 0.3),
                }
            )
            self.logger.info(
                "submission.doc.classified",
                filename=filename,
                doc_type=doc_type,
            )
        return classified

    async def _extract_data(self, classified_docs: list[dict[str, Any]], lob: str) -> dict[str, Any]:
        """Extract structured fields from classified documents.

        Uses pre-existing ``extracted_data`` when available; otherwise
        returns the union of all document metadata (the real
        implementation would invoke Document Intelligence).
        """
        extracted: dict[str, Any] = {}
        for doc in classified_docs:
            if doc.get("extracted_data"):
                extracted.update(doc["extracted_data"])
            elif doc.get("metadata"):
                extracted.update(doc["metadata"])

        self.logger.info("submission.data.extracted", field_count=len(extracted))
        return extracted

    async def _validate_completeness(self, extracted: dict[str, Any], lob: str) -> dict[str, Any]:
        """Check extracted data against product requirements."""
        required = REQUIRED_FIELDS_BY_LOB.get(lob, [])
        present = [f for f in required if f in extracted and extracted[f] is not None]
        missing = [f for f in required if f not in present]

        completeness = len(present) / len(required) if required else 1.0

        result = {
            "is_complete": len(missing) == 0,
            "completeness_pct": round(completeness * 100, 1),
            "present_fields": present,
            "missing_fields": missing,
        }
        self.logger.info(
            "submission.validation",
            complete=result["is_complete"],
            pct=result["completeness_pct"],
        )
        return result

    async def _triage(self, extracted: dict[str, Any], lob: str) -> dict[str, Any]:
        """Appetite matching, risk scoring, and priority assignment."""
        appetite_match = self._check_appetite(extracted, lob)
        risk_score = self._compute_risk_score(extracted, lob)
        priority = self._assign_priority(appetite_match, risk_score)

        triage_result = {
            "appetite_match": appetite_match,
            "risk_score": risk_score,
            "priority": priority,
            "decline_reason": (None if appetite_match else "outside_appetite_guidelines"),
        }
        self.logger.info(
            "submission.triage",
            appetite=appetite_match,
            risk_score=risk_score,
            priority=priority,
        )
        return triage_result

    # ------------------------------------------------------------------
    # Helper / heuristic methods
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_classify(filename: str) -> str:
        """Rule-based document classification fallback."""
        mapping = {
            "acord": "acord_application",
            "application": "acord_application",
            "loss_run": "loss_run",
            "lossrun": "loss_run",
            "financial": "financial_statement",
            "supplement": "supplemental",
            "sov": "sov",
            "schedule_of_values": "sov",
            "prior_policy": "prior_policy",
        }
        for token, doc_type in mapping.items():
            if token in filename:
                return doc_type
        return "unknown"

    @staticmethod
    def _check_appetite(extracted: dict[str, Any], lob: str) -> bool:
        """Return whether the submission matches appetite guidelines."""
        rules = APPETITE_RULES.get(lob)
        if not rules:
            return True

        revenue = extracted.get("annual_revenue")
        if revenue is not None:
            revenue = Decimal(str(revenue))
            if "min_revenue" in rules and revenue < rules["min_revenue"]:
                return False
            if "max_revenue" in rules and revenue > rules["max_revenue"]:
                return False

        sic = extracted.get("industry_sic_code", "")
        if sic in rules.get("excluded_sic_codes", []):
            return False

        prior = extracted.get("prior_incidents", 0)
        return not prior > rules.get("max_prior_incidents", 999)

    @staticmethod
    def _compute_risk_score(extracted: dict[str, Any], lob: str) -> float:
        """Heuristic risk score 0.0 – 10.0 (higher = riskier)."""
        score = 5.0

        if lob == "cyber":
            if not extracted.get("has_mfa", False):
                score += 1.5
            if not extracted.get("has_endpoint_protection", False):
                score += 1.0
            if not extracted.get("has_backup_strategy", False):
                score += 0.8
            if not extracted.get("has_incident_response_plan", False):
                score += 0.7
            prior = int(extracted.get("prior_incidents", 0))
            score += min(prior * 0.5, 2.0)

        revenue = extracted.get("annual_revenue")
        if revenue is not None:
            rev = float(Decimal(str(revenue)))
            if rev > 1_000_000_000:
                score += 1.0
            elif rev < 5_000_000:
                score -= 0.5

        return round(min(max(score, 0.0), 10.0), 2)

    @staticmethod
    def _assign_priority(appetite_match: bool, risk_score: float) -> int:
        """Assign priority 1 (highest) – 5 (lowest)."""
        if not appetite_match:
            return 5
        if risk_score <= 3.0:
            return 1
        if risk_score <= 5.0:
            return 2
        if risk_score <= 7.0:
            return 3
        if risk_score <= 9.0:
            return 4
        return 5

    def _overall_confidence(
        self,
        classified: list[dict[str, Any]],
        validation: dict[str, Any],
        triage: dict[str, Any],
    ) -> float:
        """Compute aggregate confidence for the submission pipeline."""
        doc_conf = sum(d.get("classification_confidence", 0.5) for d in classified) / max(len(classified), 1)
        completeness = validation.get("completeness_pct", 0) / 100.0
        triage_conf = 0.9 if triage.get("appetite_match") else 0.5

        return round((doc_conf * 0.3 + completeness * 0.4 + triage_conf * 0.3), 4)
