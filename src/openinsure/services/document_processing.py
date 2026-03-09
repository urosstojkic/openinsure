"""Document processing service.

Stub implementation to be backed by Azure AI Document Intelligence.
Provides document classification, data extraction, and document generation.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from openinsure.domain.common import new_id

logger = structlog.get_logger()


class DocumentType(StrEnum):
    """Supported document types."""

    acord_application = "acord_application"
    loss_run = "loss_run"
    financial_statement = "financial_statement"
    supplemental = "supplemental"
    schedule_of_values = "schedule_of_values"
    prior_policy = "prior_policy"
    quote_letter = "quote_letter"
    declarations_page = "declarations_page"
    policy_form = "policy_form"
    endorsement = "endorsement"
    certificate = "certificate"
    fnol_report = "fnol_report"
    unknown = "unknown"


class ClassificationResult(BaseModel):
    """Result of document classification."""

    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Result of structured data extraction from a document."""

    document_type: DocumentType
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str = ""
    warnings: list[str] = Field(default_factory=list)


class GeneratedDocument(BaseModel):
    """Result of document generation."""

    document_id: str = Field(default_factory=lambda: str(new_id()))
    document_type: DocumentType
    content: bytes = b""
    content_type: str = "application/pdf"
    filename: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentProcessingService:
    """Service for document classification, extraction, and generation.

    This is a stub implementation. In production, methods will delegate
    to Azure AI Document Intelligence for classification and extraction,
    and to a template engine for document generation.
    """

    def classify_document(
        self,
        file_content: bytes,
        filename: str = "",
    ) -> ClassificationResult:
        """Classify a document by its content.

        Stub: uses filename heuristics until Azure AI integration.
        """
        lower = filename.lower()
        doc_type = DocumentType.unknown
        confidence = 0.3

        heuristic_map: dict[str, DocumentType] = {
            "acord": DocumentType.acord_application,
            "loss_run": DocumentType.loss_run,
            "lossrun": DocumentType.loss_run,
            "financial": DocumentType.financial_statement,
            "supplement": DocumentType.supplemental,
            "sov": DocumentType.schedule_of_values,
            "prior_policy": DocumentType.prior_policy,
            "quote": DocumentType.quote_letter,
            "declaration": DocumentType.declarations_page,
            "policy_form": DocumentType.policy_form,
            "endorsement": DocumentType.endorsement,
            "certificate": DocumentType.certificate,
            "fnol": DocumentType.fnol_report,
        }

        for keyword, dtype in heuristic_map.items():
            if keyword in lower:
                doc_type = dtype
                confidence = 0.6
                break

        logger.info(
            "document.classified",
            filename=filename,
            document_type=doc_type.value,
            confidence=confidence,
        )

        return ClassificationResult(
            document_type=doc_type,
            confidence=confidence,
            metadata={"filename": filename, "size_bytes": len(file_content)},
        )

    def extract_data(
        self,
        file_content: bytes,
        document_type: DocumentType,
    ) -> ExtractionResult:
        """Extract structured data from a document.

        Stub: returns empty extraction until Azure AI integration.
        """
        logger.info(
            "document.extract_requested",
            document_type=document_type.value,
            size_bytes=len(file_content),
        )

        return ExtractionResult(
            document_type=document_type,
            extracted_fields={},
            confidence=0.0,
            raw_text="",
            warnings=["Stub implementation — no extraction performed"],
        )

    def generate_document(
        self,
        document_type: DocumentType,
        data: dict[str, Any],
    ) -> GeneratedDocument:
        """Generate a document from structured data.

        Stub: returns a placeholder until template engine integration.
        """
        filename = f"{document_type.value}_{str(new_id())[:8]}.pdf"

        logger.info(
            "document.generated",
            document_type=document_type.value,
            filename=filename,
        )

        return GeneratedDocument(
            document_type=document_type,
            content=b"",
            content_type="application/pdf",
            filename=filename,
        )
