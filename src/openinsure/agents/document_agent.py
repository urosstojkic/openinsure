"""Document processing agent for OpenInsure.

Handles document classification, structured data extraction from
insurance documents, and document generation (quotes, policies,
certificates).
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog

from openinsure.agents.base import AgentCapability, AgentConfig, InsuranceAgent

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Document type registry
# ---------------------------------------------------------------------------

DOCUMENT_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    "acord_application": {
        "display_name": "ACORD Application",
        "expected_fields": [
            "applicant_name",
            "address",
            "effective_date",
            "line_of_business",
            "requested_limits",
        ],
        "keywords": ["acord", "application", "125", "126", "130"],
    },
    "loss_run": {
        "display_name": "Loss Run Report",
        "expected_fields": [
            "carrier",
            "policy_period",
            "claims",
            "total_incurred",
        ],
        "keywords": ["loss run", "loss history", "claims history"],
    },
    "financial_statement": {
        "display_name": "Financial Statement",
        "expected_fields": [
            "company_name",
            "revenue",
            "total_assets",
            "net_income",
            "fiscal_year",
        ],
        "keywords": ["financial", "balance sheet", "income statement", "10-k"],
    },
    "supplemental": {
        "display_name": "Supplemental Application",
        "expected_fields": [
            "applicant_name",
            "supplemental_questions",
            "signed_date",
        ],
        "keywords": ["supplemental", "supplement", "questionnaire"],
    },
    "sov": {
        "display_name": "Schedule of Values",
        "expected_fields": [
            "locations",
            "building_values",
            "contents_values",
            "business_income_values",
        ],
        "keywords": ["schedule of values", "sov", "tiv"],
    },
    "prior_policy": {
        "display_name": "Prior Policy",
        "expected_fields": [
            "carrier",
            "policy_number",
            "effective_date",
            "expiration_date",
            "premium",
            "limits",
        ],
        "keywords": ["declarations", "dec page", "prior policy"],
    },
    "quote_document": {
        "display_name": "Quote Document",
        "expected_fields": [
            "insured_name",
            "premium",
            "limits",
            "deductible",
            "effective_date",
        ],
        "keywords": ["quote", "proposal", "indication"],
    },
    "policy_document": {
        "display_name": "Policy Document",
        "expected_fields": [
            "policy_number",
            "insured_name",
            "coverages",
            "premium",
            "effective_date",
        ],
        "keywords": ["policy", "binder", "certificate"],
    },
    "certificate": {
        "display_name": "Certificate of Insurance",
        "expected_fields": [
            "certificate_holder",
            "insured",
            "policy_number",
            "coverages",
            "limits",
        ],
        "keywords": ["certificate", "coi", "acord 25"],
    },
}

# Templates for document generation
DOCUMENT_TEMPLATES: dict[str, str] = {
    "quote": "quote_template_v2",
    "declarations": "declarations_template_v1",
    "policy_form": "policy_form_template_v1",
    "certificate": "certificate_template_v1",
    "endorsement": "endorsement_template_v1",
    "cancellation_notice": "cancellation_notice_template_v1",
}


class DocumentAgent(InsuranceAgent):
    """Document classification, extraction, and generation agent.

    Supported task types dispatched by :meth:`process`:
    - ``classify`` – identify the type of a submitted document.
    - ``extract`` – pull structured data from a classified document.
    - ``generate`` – produce an insurance document from structured data.
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(
            config
            or AgentConfig(
                agent_id="document_agent",
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
                name="classify_document",
                description="Classify an insurance document by type",
                required_inputs=["document"],
                produces=["document_type", "classification_confidence"],
            ),
            AgentCapability(
                name="extract_data",
                description="Extract structured data from an insurance document",
                required_inputs=["document", "document_type"],
                produces=["extracted_data"],
            ),
            AgentCapability(
                name="generate_document",
                description="Generate an insurance document from structured data",
                required_inputs=["document_type", "data"],
                produces=["document_url", "document_id"],
            ),
        ]

    # ------------------------------------------------------------------
    # Main processing entry-point
    # ------------------------------------------------------------------

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = task.get("type", "classify")
        handler = {
            "classify": self._classify,
            "extract": self._extract,
            "generate": self._generate,
        }.get(task_type)

        if handler is None:
            raise ValueError(f"Unknown document task type: {task_type}")

        self.logger.info("document.task.dispatch", task_type=task_type)
        return await handler(task)

    # ------------------------------------------------------------------
    # Classify
    # ------------------------------------------------------------------

    async def _classify(self, task: dict[str, Any]) -> dict[str, Any]:
        """Classify a document into a known insurance document type."""
        document = task.get("document", {})
        filename = document.get("filename", "").lower()
        content_hint = document.get("content_hint", "").lower()

        best_type = "unknown"
        best_score = 0.0

        for doc_type, meta in DOCUMENT_TYPE_REGISTRY.items():
            score = self._score_classification(filename, content_hint, meta.get("keywords", []))
            if score > best_score:
                best_score = score
                best_type = doc_type

        confidence = min(best_score, 1.0)

        self.logger.info(
            "document.classified",
            filename=filename,
            doc_type=best_type,
            confidence=confidence,
        )

        return {
            "document_type": best_type,
            "display_name": DOCUMENT_TYPE_REGISTRY.get(best_type, {}).get("display_name", best_type),
            "classification_confidence": confidence,
            "expected_fields": DOCUMENT_TYPE_REGISTRY.get(best_type, {}).get("expected_fields", []),
            "confidence": confidence,
            "reasoning": {
                "step": "classify",
                "filename": filename,
                "matched_type": best_type,
            },
            "data_sources": ["document_metadata"],
            "knowledge_queries": ["document_type_registry"],
        }

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------

    async def _extract(self, task: dict[str, Any]) -> dict[str, Any]:
        """Extract structured data from a classified document.

        In production this invokes Azure Document Intelligence.  The
        stub returns pre-existing extracted data or an empty skeleton
        based on expected fields.
        """
        document = task.get("document", {})
        doc_type = task.get("document_type") or document.get("document_type", "unknown")

        # Use pre-extracted data if available
        if document.get("extracted_data"):
            extracted = document["extracted_data"]
        else:
            expected = DOCUMENT_TYPE_REGISTRY.get(doc_type, {}).get("expected_fields", [])
            extracted = dict.fromkeys(expected)

        # Compute extraction completeness
        total = len(extracted)
        filled = sum(1 for v in extracted.values() if v is not None)
        completeness = filled / max(total, 1)

        self.logger.info(
            "document.extracted",
            doc_type=doc_type,
            fields=total,
            filled=filled,
        )

        return {
            "document_type": doc_type,
            "extracted_data": extracted,
            "extraction_completeness": round(completeness, 4),
            "missing_fields": [k for k, v in extracted.items() if v is None],
            "confidence": round(0.5 + completeness * 0.45, 4),
            "reasoning": {
                "step": "extract",
                "doc_type": doc_type,
                "completeness": round(completeness, 4),
            },
            "data_sources": ["document_content", "document_intelligence"],
            "knowledge_queries": [f"extraction_schema/{doc_type}"],
        }

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    async def _generate(self, task: dict[str, Any]) -> dict[str, Any]:
        """Generate an insurance document from structured data.

        Selects the appropriate template, merges data, and returns a
        document reference.  In production this calls the document
        rendering service and stores the output in Blob Storage.
        """
        doc_type = task.get("document_type", "quote")
        data = task.get("data", {})

        template = DOCUMENT_TEMPLATES.get(doc_type)
        if template is None:
            raise ValueError(f"No template registered for document type: {doc_type}")

        doc_id = str(uuid4())
        now = datetime.now(UTC)
        storage_url = f"https://openinsure.blob.core.windows.net/documents/{doc_type}/{doc_id}.pdf"

        self.logger.info(
            "document.generated",
            doc_type=doc_type,
            doc_id=doc_id,
            template=template,
        )

        return {
            "document_id": doc_id,
            "document_type": doc_type,
            "template_used": template,
            "storage_url": storage_url,
            "generated_at": now.isoformat(),
            "data_fields_used": list(data.keys()),
            "confidence": 0.95,
            "reasoning": {
                "step": "generate",
                "doc_type": doc_type,
                "template": template,
            },
            "data_sources": ["structured_data", "document_templates"],
            "knowledge_queries": [f"template/{doc_type}"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_classification(filename: str, content_hint: str, keywords: list[str]) -> float:
        """Score how well a document matches a type based on keywords."""
        score = 0.0
        combined = f"{filename} {content_hint}"
        for kw in keywords:
            if kw in combined:
                score += 0.35
        return min(score, 1.0)
