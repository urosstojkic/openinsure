"""Document upload/download API endpoints."""

import re

import structlog
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from openinsure.infrastructure.factory import get_blob_storage

router = APIRouter()
logger = structlog.get_logger()

# Allowed characters in blob paths: alphanumeric, dash, underscore, dot, forward-slash
_SAFE_BLOB_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/ -]{0,1023}$")


def _sanitize_blob_name(blob_name: str) -> str:
    """Validate and sanitize a blob name to prevent path traversal.

    Rejects paths containing ``..``, absolute paths, backslashes,
    and any characters outside the safe set.

    Raises:
        HTTPException: If the blob_name is invalid.
    """
    if not blob_name or not blob_name.strip():
        raise HTTPException(400, "blob_name cannot be empty")
    # Reject path traversal sequences
    if ".." in blob_name:
        raise HTTPException(400, "Path traversal not allowed: blob_name must not contain '..'")
    # Reject absolute paths (Unix or Windows)
    if blob_name.startswith(("/", "\\")) or (len(blob_name) >= 2 and blob_name[1] == ":"):
        raise HTTPException(400, "Absolute paths not allowed in blob_name")
    # Reject backslashes
    if "\\" in blob_name:
        raise HTTPException(400, "Backslashes not allowed in blob_name")
    # Validate against safe pattern
    if not _SAFE_BLOB_RE.match(blob_name):
        raise HTTPException(400, "blob_name contains invalid characters")
    return blob_name


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    submission_id: str | None = Query(None),
    policy_id: str | None = Query(None),
    claim_id: str | None = Query(None),
    document_type: str = Query("other"),
) -> dict[str, object]:
    """Upload a document, classify it, and extract data via Document Intelligence."""
    from openinsure.services.document_processing import DocumentProcessingService, DocumentType

    max_upload_size = 50 * 1024 * 1024  # 50 MB
    content = await file.read()
    if len(content) > max_upload_size:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    filename = file.filename or "untitled"
    svc = DocumentProcessingService()

    # Classify
    classification = svc.classify_document(content, filename)
    detected_type = classification.document_type.value
    if document_type == "other":
        document_type = detected_type

    # Extract data (async — uses DI when available, regex fallback otherwise)
    try:
        doc_type_enum = (
            DocumentType(document_type) if document_type in DocumentType.__members__ else DocumentType.unknown
        )
    except ValueError:
        doc_type_enum = DocumentType.unknown

    extraction = await svc.extract_data_async(
        content,
        doc_type_enum,
        content_type=file.content_type or "application/octet-stream",
    )

    # Upload to storage
    storage = get_blob_storage()
    upload_result: dict[str, object] = {}
    if storage:
        entity_id = submission_id or policy_id or claim_id or "unattached"
        blob_name = f"{document_type}/{entity_id}/{filename}"
        upload_result = await storage.upload_document(
            blob_name=blob_name,
            data=content,
            content_type=file.content_type or "application/octet-stream",
            metadata={
                "submission_id": submission_id or "",
                "policy_id": policy_id or "",
                "claim_id": claim_id or "",
                "document_type": document_type,
                "original_filename": filename,
                "detected_type": detected_type,
                "extraction_confidence": str(extraction.confidence),
            },
        )

    return {
        "filename": filename,
        "blob_name": upload_result.get("blob_name", f"{document_type}/{filename}"),
        "size": len(content),
        "storage": "azure" if storage else "memory",
        "url": upload_result.get("url", f"/documents/{filename}"),
        "classification": {
            "document_type": detected_type,
            "confidence": classification.confidence,
        },
        "extraction": {
            "fields": extraction.extracted_fields,
            "confidence": extraction.confidence,
            "warnings": extraction.warnings,
            "source": "document_intelligence" if extraction.confidence > 0.6 else "fallback",
        },
    }


@router.get("/list")
async def list_documents(
    prefix: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """List documents in storage."""
    storage = get_blob_storage()
    if not storage:
        return {"items": [], "storage": "memory"}

    docs = await storage.list_documents(prefix=prefix, limit=limit)
    return {"items": docs, "storage": "azure"}


@router.get("/download/{blob_name:path}")
async def get_document_url(blob_name: str) -> dict[str, str]:
    """Get a time-limited download URL for a document."""
    blob_name = _sanitize_blob_name(blob_name)
    storage = get_blob_storage()
    if not storage:
        raise HTTPException(404, "Document storage not configured")

    try:
        url = await storage.get_document_url(blob_name, expiry_hours=1)
        return {"blob_name": blob_name, "download_url": url}
    except Exception as e:
        raise HTTPException(404, f"Document not found: {e}")
