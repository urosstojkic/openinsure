"""Unit tests for document processing service — classification, extraction, generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openinsure.services.document_processing import (
    ClassificationResult,
    DocumentProcessingService,
    DocumentType,
    ExtractionResult,
    GeneratedDocument,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(di_available: bool = False) -> DocumentProcessingService:
    """Create a DocumentProcessingService with optional DI mock."""
    with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
        if di_available:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_get.return_value = mock_di
        else:
            mock_get.return_value = None
        svc = DocumentProcessingService()
    return svc


# ---------------------------------------------------------------------------
# classify_document
# ---------------------------------------------------------------------------

class TestClassifyDocument:
    def test_acord_keyword(self):
        svc = _service()
        result = svc.classify_document(b"some content", "ACORD_application.pdf")
        assert result.document_type == DocumentType.acord_application
        assert result.confidence == 0.6

    def test_loss_run_keyword(self):
        svc = _service()
        result = svc.classify_document(b"data", "loss_run_report.pdf")
        assert result.document_type == DocumentType.loss_run

    def test_financial_keyword(self):
        svc = _service()
        result = svc.classify_document(b"data", "financial_statement_2024.pdf")
        assert result.document_type == DocumentType.financial_statement

    def test_unknown_filename(self):
        svc = _service()
        result = svc.classify_document(b"data", "random_file.pdf")
        assert result.document_type == DocumentType.unknown
        assert result.confidence == 0.3

    def test_empty_filename(self):
        svc = _service()
        result = svc.classify_document(b"data", "")
        assert result.document_type == DocumentType.unknown

    def test_di_boosts_confidence(self):
        """When DI is available, confidence gets +0.2 boost."""
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()
        result = svc.classify_document(b"data", "ACORD_form.pdf")
        assert result.confidence == 0.8  # 0.6 + 0.2

    def test_di_boost_capped(self):
        """Confidence capped at 0.95 even with DI boost."""
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()
        # Even with DI boost on keyword match, should not exceed 0.95
        result = svc.classify_document(b"data", "acord_form.pdf")
        assert result.confidence <= 0.95

    def test_metadata_includes_filename_and_size(self):
        svc = _service()
        content = b"hello"
        result = svc.classify_document(content, "test.pdf")
        assert result.metadata["filename"] == "test.pdf"
        assert result.metadata["size_bytes"] == 5

    def test_case_insensitive_matching(self):
        svc = _service()
        result = svc.classify_document(b"data", "FNOL_Report.PDF")
        assert result.document_type == DocumentType.fnol_report

    def test_all_document_types_reachable(self):
        """Every keyword in the heuristic map should produce its document type."""
        svc = _service()
        cases = {
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
        for keyword, expected_type in cases.items():
            result = svc.classify_document(b"x", f"{keyword}_test.pdf")
            assert result.document_type == expected_type, f"Failed for keyword '{keyword}'"


# ---------------------------------------------------------------------------
# extract_data_async
# ---------------------------------------------------------------------------

class TestExtractDataAsync:
    @pytest.mark.asyncio
    async def test_with_di_available(self):
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_di.analyze_document = AsyncMock(return_value={
                "key_value_pairs": [{"key": "Policy Number", "value": "POL-123"}],
                "fields": {"applicant": "Acme Corp"},
                "text": "Full document text here",
            })
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()

        result = await svc.extract_data_async(b"content", DocumentType.acord_application)
        assert result.extracted_fields["Policy Number"] == "POL-123"
        assert result.extracted_fields["applicant"] == "Acme Corp"
        assert result.confidence == 0.85
        assert "Full document text" in result.raw_text

    @pytest.mark.asyncio
    async def test_di_empty_fields_low_confidence(self):
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_di.analyze_document = AsyncMock(return_value={
                "key_value_pairs": [],
                "fields": {},
                "text": "",
            })
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()

        result = await svc.extract_data_async(b"content", DocumentType.unknown)
        assert result.confidence == 0.4

    @pytest.mark.asyncio
    async def test_di_failure_falls_back(self):
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_di.analyze_document = AsyncMock(side_effect=RuntimeError("DI down"))
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()

        with patch("openinsure.infrastructure.document_intelligence._fallback_analyze", return_value={
            "key_value_pairs": [{"key": "Name", "value": "Fallback"}],
            "text": "fallback text",
        }):
            result = await svc.extract_data_async(b"content", DocumentType.acord_application)
        assert result.extracted_fields.get("Name") == "Fallback"

    @pytest.mark.asyncio
    async def test_no_di_uses_fallback(self):
        svc = _service(di_available=False)
        with patch("openinsure.infrastructure.document_intelligence._fallback_analyze", return_value={
            "key_value_pairs": [],
            "text": "",
        }):
            result = await svc.extract_data_async(b"data", DocumentType.loss_run)
        assert result.confidence == 0.0
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_raw_text_truncated(self):
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_di.analyze_document = AsyncMock(return_value={
                "key_value_pairs": [{"key": "k", "value": "v"}],
                "fields": {},
                "text": "x" * 10000,
            })
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()
        result = await svc.extract_data_async(b"content", DocumentType.unknown)
        assert len(result.raw_text) <= 5000


# ---------------------------------------------------------------------------
# extract_data (synchronous)
# ---------------------------------------------------------------------------

class TestExtractData:
    def test_sync_extraction_uses_fallback(self):
        svc = _service()
        with patch("openinsure.infrastructure.document_intelligence._fallback_analyze", return_value={
            "key_value_pairs": [{"key": "Applicant", "value": "Test Inc"}],
            "text": "Some text",
        }):
            result = svc.extract_data(b"pdf bytes", DocumentType.acord_application)
        assert result.extracted_fields["Applicant"] == "Test Inc"
        assert result.confidence == 0.5

    def test_sync_empty_extraction(self):
        svc = _service()
        with patch("openinsure.infrastructure.document_intelligence._fallback_analyze", return_value={
            "key_value_pairs": [],
            "text": "",
        }):
            result = svc.extract_data(b"data", DocumentType.unknown)
        assert result.confidence == 0.0
        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# generate_document
# ---------------------------------------------------------------------------

class TestGenerateDocument:
    def test_generates_placeholder(self):
        svc = _service()
        result = svc.generate_document(DocumentType.quote_letter, {"applicant": "Acme"})
        assert isinstance(result, GeneratedDocument)
        assert result.document_type == DocumentType.quote_letter
        assert result.content_type == "application/pdf"
        assert result.filename.startswith("quote_letter_")
        assert result.filename.endswith(".pdf")

    def test_document_id_generated(self):
        svc = _service()
        r1 = svc.generate_document(DocumentType.certificate, {})
        r2 = svc.generate_document(DocumentType.certificate, {})
        assert r1.document_id != r2.document_id

    def test_generated_at_populated(self):
        svc = _service()
        result = svc.generate_document(DocumentType.endorsement, {})
        assert result.generated_at is not None


# ---------------------------------------------------------------------------
# Adversarial / edge-case tests
# ---------------------------------------------------------------------------

class TestDocumentProcessingAdversarial:
    """Tests that try to break document processing with hostile inputs."""

    def test_classify_empty_content(self):
        """Empty file content should still classify (by filename)."""
        svc = _service()
        result = svc.classify_document(b"", "acord_form.pdf")
        assert result.document_type == DocumentType.acord_application
        assert result.metadata["size_bytes"] == 0

    def test_classify_huge_content(self):
        """Large content should not crash classification."""
        svc = _service()
        result = svc.classify_document(b"x" * 10_000_000, "unknown.pdf")
        assert result.metadata["size_bytes"] == 10_000_000

    def test_classify_unicode_filename(self):
        """Unicode in filename should not crash."""
        svc = _service()
        result = svc.classify_document(b"data", "声明_declaration_页.pdf")
        assert result.document_type == DocumentType.declarations_page

    def test_classify_path_traversal_filename(self):
        """Malicious filename should not cause issues."""
        svc = _service()
        result = svc.classify_document(b"data", "../../etc/passwd")
        assert result.document_type == DocumentType.unknown

    @pytest.mark.asyncio
    async def test_extract_async_di_returns_empty_kv(self):
        """DI returns key_value_pairs with empty key → should skip."""
        with patch("openinsure.infrastructure.factory.get_document_intelligence") as mock_get:
            mock_di = MagicMock()
            mock_di.is_available = True
            mock_di.analyze_document = AsyncMock(return_value={
                "key_value_pairs": [
                    {"key": "", "value": "orphan"},
                    {"key": "  ", "value": "whitespace"},
                    {"key": "valid", "value": "ok"},
                ],
                "fields": {},
                "text": "text",
            })
            mock_get.return_value = mock_di
            svc = DocumentProcessingService()

        result = await svc.extract_data_async(b"content", DocumentType.unknown)
        assert "valid" in result.extracted_fields
        # Empty string key stripped → not included
        assert "" not in result.extracted_fields

    def test_generate_different_types(self):
        """Generate documents of every type to verify no crashes."""
        svc = _service()
        for doc_type in DocumentType:
            result = svc.generate_document(doc_type, {"key": "value"})
            assert result.document_type == doc_type
            assert result.filename.endswith(".pdf")

    def test_extract_sync_with_binary_content(self):
        """Binary content (non-text) should not crash sync extraction."""
        svc = _service()
        binary = bytes(range(256))  # All byte values
        with patch("openinsure.infrastructure.document_intelligence._fallback_analyze", return_value={
            "key_value_pairs": [],
            "text": "",
        }):
            result = svc.extract_data(binary, DocumentType.unknown)
        assert result.confidence == 0.0
