"""Azure AI Document Intelligence adapter for OpenInsure.

Provides document analysis (OCR + structured extraction) for insurance
documents — ACORD forms, loss runs, financial statements, policy pages,
FNOL reports, etc.

Uses the prebuilt ``document`` model by default, which handles mixed
document types.  Falls back to local heuristic extraction when the
service is unavailable.

Configuration:
    OPENINSURE_DOCUMENT_INTELLIGENCE_ENDPOINT — Azure DI resource endpoint
    Authentication: DefaultAzureCredential (Managed Identity / CLI)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DocumentIntelligenceAdapter:
    """Async-friendly wrapper around Azure AI Document Intelligence.

    Parameters
    ----------
    endpoint:
        The Azure Document Intelligence resource endpoint URL.
    model_id:
        The model to use for analysis.  Defaults to ``"prebuilt-document"``
        which extracts key-value pairs, tables, and text from any document.
    """

    def __init__(self, endpoint: str, model_id: str = "prebuilt-document") -> None:
        self._endpoint = endpoint
        self._model_id = model_id
        self._client: Any = None
        self._available = False

        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.identity import DefaultAzureCredential

            self._client = DocumentIntelligenceClient(
                endpoint=endpoint,
                credential=DefaultAzureCredential(),
            )
            self._available = True
            logger.info("document_intelligence.connected", endpoint=endpoint)
        except Exception as exc:
            logger.warning("document_intelligence.unavailable", error=str(exc))

    @property
    def is_available(self) -> bool:
        return self._available

    async def analyze_document(
        self,
        content: bytes,
        *,
        content_type: str = "application/pdf",
    ) -> dict[str, Any]:
        """Analyze a document and return extracted data.

        Returns a dict with:
        - ``pages``: number of pages
        - ``text``: full extracted text
        - ``key_value_pairs``: list of {key, value, confidence} dicts
        - ``tables``: list of extracted tables
        - ``fields``: dict of typed field extractions
        """
        if not self._available or self._client is None:
            return _fallback_analyze(content, content_type)

        try:
            import asyncio
            from functools import partial

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                partial(self._sync_analyze, content, content_type),
            )
        except Exception as exc:
            logger.warning("document_intelligence.analyze_failed", error=str(exc))
            return _fallback_analyze(content, content_type)

    def _sync_analyze(self, content: bytes, content_type: str) -> dict[str, Any]:
        """Synchronous analysis — runs in executor."""
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

        poller = self._client.begin_analyze_document(
            model_id=self._model_id,
            body=AnalyzeDocumentRequest(bytes_source=content),
            content_type=content_type,
        )
        result = poller.result()

        # Extract key-value pairs
        kv_pairs: list[dict[str, Any]] = []
        for kv in getattr(result, "key_value_pairs", []) or []:
            key_text = kv.key.content if kv.key else ""
            val_text = kv.value.content if kv.value else ""
            kv_pairs.append(
                {
                    "key": key_text,
                    "value": val_text,
                    "confidence": kv.confidence or 0.0,
                }
            )

        # Extract tables
        tables: list[dict[str, Any]] = []
        for table in getattr(result, "tables", []) or []:
            rows: list[list[str]] = []
            for cell in table.cells or []:
                while len(rows) <= cell.row_index:
                    rows.append([])
                while len(rows[cell.row_index]) <= cell.column_index:
                    rows[cell.row_index].append("")
                rows[cell.row_index][cell.column_index] = cell.content or ""
            tables.append(
                {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "rows": rows,
                }
            )

        # Collect full text
        pages = getattr(result, "pages", []) or []
        full_text = ""
        for page in pages:
            for line in getattr(page, "lines", []) or []:
                full_text += (line.content or "") + "\n"

        # Extract document-level fields (prebuilt models)
        fields: dict[str, Any] = {}
        doc_fields = (
            (getattr(result, "documents", [None]) or [None])[0].fields.items()
            if hasattr(result, "documents") and result.documents
            else []
        )
        for name, field in doc_fields:
            fields[name] = {
                "value": (
                    field.content if hasattr(field, "content") else str(field.value) if hasattr(field, "value") else ""
                ),
                "confidence": (field.confidence if hasattr(field, "confidence") else 0.0),
            }

        return {
            "pages": len(pages),
            "text": full_text,
            "key_value_pairs": kv_pairs,
            "tables": tables,
            "fields": fields,
            "source": "azure_document_intelligence",
        }

    async def close(self) -> None:
        if self._client:
            self._client.close()


# ---------------------------------------------------------------------------
# Fallback extraction when Document Intelligence is unavailable
# ---------------------------------------------------------------------------


def _fallback_analyze(content: bytes, _content_type: str) -> dict[str, Any]:
    """Best-effort extraction without Azure AI Document Intelligence.

    Attempts to extract text from the raw bytes and identify insurance-
    specific key-value patterns using regex.
    """
    text = ""

    # Try to decode as text (for plain text, XML, or simple PDFs)
    for encoding in ("utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue

    # Extract key-value pairs from text using common patterns
    kv_pairs: list[dict[str, Any]] = []
    if text:
        # Common insurance form patterns: "Key: Value" or "Key  Value"
        patterns = [
            (r"(?i)applicant\s*(?:name)?[:\s]+(.+?)(?:\n|$)", "applicant_name"),
            (r"(?i)insured\s*(?:name)?[:\s]+(.+?)(?:\n|$)", "insured_name"),
            (r"(?i)policy\s*(?:number|#|no\.?)[:\s]+(\S+)", "policy_number"),
            (r"(?i)effective\s*date[:\s]+(\S+)", "effective_date"),
            (r"(?i)expiration\s*date[:\s]+(\S+)", "expiration_date"),
            (r"(?i)premium[:\s]+\$?([\d,]+\.?\d*)", "premium"),
            (r"(?i)limit[:\s]+\$?([\d,]+\.?\d*)", "limit"),
            (r"(?i)deductible[:\s]+\$?([\d,]+\.?\d*)", "deductible"),
            (r"(?i)annual\s*revenue[:\s]+\$?([\d,]+\.?\d*)", "annual_revenue"),
            (r"(?i)employee\s*(?:count|#|number)[:\s]+(\d+)", "employee_count"),
            (r"(?i)SIC\s*(?:code)?[:\s]+(\d{4})", "sic_code"),
            (r"(?i)NAICS\s*(?:code)?[:\s]+(\d{4,6})", "naics_code"),
            (r"(?i)date\s*of\s*loss[:\s]+(\S+)", "date_of_loss"),
            (r"(?i)claim\s*(?:number|#|no\.?)[:\s]+(\S+)", "claim_number"),
        ]
        for pattern, key in patterns:
            match = re.search(pattern, text)
            if match:
                kv_pairs.append(
                    {
                        "key": key,
                        "value": match.group(1).strip().rstrip(",;"),
                        "confidence": 0.5,
                    }
                )

    return {
        "pages": max(1, text.count("\f") + 1) if text else 0,
        "text": text[:10000],  # Cap at 10K chars
        "key_value_pairs": kv_pairs,
        "tables": [],
        "fields": {},
        "source": "fallback_regex",
    }
