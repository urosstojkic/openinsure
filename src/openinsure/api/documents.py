"""Document upload/download API endpoints.

Provides both blob-storage operations (upload, list, download) and
relational document record CRUD for the polymorphic ``documents`` table.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from openinsure.infrastructure.factory import get_blob_storage

router = APIRouter()
logger = structlog.get_logger()

# Allowed characters in blob paths: alphanumeric, dash, underscore, dot, forward-slash
_SAFE_BLOB_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/ -]{0,1023}$")

# In-memory store for document records (production → SQL via documents table)
_document_records: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Request / Response models for document records
# ---------------------------------------------------------------------------


class DocumentRecordCreate(BaseModel):
    """Payload for creating a document record."""

    entity_type: str = Field(..., min_length=1, description="Entity type: submission, policy, claim, endorsement")
    entity_id: str = Field(..., min_length=1, description="UUID of the related entity")
    document_type: str = Field(..., min_length=1, description="Document classification")
    filename: str = Field(..., min_length=1, max_length=500)
    storage_url: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    extracted_data: dict[str, Any] | None = None
    classification_confidence: float | None = None
    uploaded_by: str | None = None


class DocumentRecordUpdate(BaseModel):
    """Payload for updating a document record."""

    document_type: str | None = None
    filename: str | None = None
    storage_url: str | None = None
    content_type: str | None = None
    extracted_data: dict[str, Any] | None = None
    classification_confidence: float | None = None


class DocumentRecordResponse(BaseModel):
    """Public representation of a document record."""

    id: str
    entity_type: str
    entity_id: str
    document_type: str
    filename: str
    storage_url: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    extracted_data: dict[str, Any] | None = None
    classification_confidence: float | None = None
    uploaded_by: str | None = None
    uploaded_at: str
    deleted_at: str | None = None


class DocumentRecordList(BaseModel):
    """Paginated list of document records."""

    items: list[DocumentRecordResponse]
    total: int
    skip: int
    limit: int


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


class BlobDocumentList(BaseModel):
    """Paginated list of blob storage documents."""

    items: list[dict[str, Any]]
    total: int
    skip: int
    limit: int
    storage: str


@router.get("/list", response_model=BlobDocumentList)
async def list_documents(
    prefix: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> BlobDocumentList:
    """List documents in storage."""
    storage = get_blob_storage()
    if not storage:
        return BlobDocumentList(items=[], total=0, skip=skip, limit=limit, storage="memory")

    docs = await storage.list_documents(prefix=prefix, limit=limit + skip)
    total = len(docs)
    page = docs[skip : skip + limit]
    return BlobDocumentList(items=page, total=total, skip=skip, limit=limit, storage="azure")


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


# ---------------------------------------------------------------------------
# Polymorphic document record CRUD (#175)
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


@router.post("/records", response_model=DocumentRecordResponse, status_code=201)
async def create_document_record(body: DocumentRecordCreate) -> DocumentRecordResponse:
    """Create a document record linked to any entity."""

    record: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "document_type": body.document_type,
        "filename": body.filename,
        "storage_url": body.storage_url,
        "content_type": body.content_type,
        "file_size_bytes": body.file_size_bytes,
        "extracted_data": body.extracted_data,
        "classification_confidence": body.classification_confidence,
        "uploaded_by": body.uploaded_by,
        "uploaded_at": _now(),
        "deleted_at": None,
    }
    _document_records.append(record)
    logger.info("document_record.created", document_id=record["id"], entity_type=body.entity_type)
    return DocumentRecordResponse(**record)


@router.get("/records", response_model=DocumentRecordList)
async def list_document_records(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    document_type: str | None = Query(None, description="Filter by document type"),
    include_deleted: bool = Query(False, description="Include soft-deleted documents"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> DocumentRecordList:
    """List document records with optional filtering."""
    items = list(_document_records)
    if not include_deleted:
        items = [d for d in items if d.get("deleted_at") is None]
    if entity_type:
        items = [d for d in items if d["entity_type"] == entity_type]
    if entity_id:
        items = [d for d in items if d["entity_id"] == entity_id]
    if document_type:
        items = [d for d in items if d["document_type"] == document_type]

    total = len(items)
    page = items[skip : skip + limit]
    return DocumentRecordList(
        items=[DocumentRecordResponse(**d) for d in page],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/records/{document_id}", response_model=DocumentRecordResponse)
async def get_document_record(document_id: str) -> DocumentRecordResponse:
    """Retrieve a single document record by ID."""
    for doc in _document_records:
        if doc["id"] == document_id:
            return DocumentRecordResponse(**doc)
    raise HTTPException(status_code=404, detail=f"Document record {document_id} not found")


@router.put("/records/{document_id}", response_model=DocumentRecordResponse)
async def update_document_record(document_id: str, body: DocumentRecordUpdate) -> DocumentRecordResponse:
    """Update a document record's mutable fields."""
    for doc in _document_records:
        if doc["id"] == document_id:
            if doc.get("deleted_at"):
                raise HTTPException(status_code=409, detail="Cannot update a deleted document")
            updates = body.model_dump(exclude_unset=True)
            for key, val in updates.items():
                if val is not None:
                    doc[key] = val
            return DocumentRecordResponse(**doc)
    raise HTTPException(status_code=404, detail=f"Document record {document_id} not found")


@router.delete("/records/{document_id}", response_model=DocumentRecordResponse)
async def delete_document_record(document_id: str) -> DocumentRecordResponse:
    """Soft-delete a document record."""
    for doc in _document_records:
        if doc["id"] == document_id:
            if doc.get("deleted_at"):
                raise HTTPException(status_code=409, detail="Document already deleted")
            doc["deleted_at"] = _now()
            logger.info("document_record.deleted", document_id=document_id)
            return DocumentRecordResponse(**doc)
    raise HTTPException(status_code=404, detail=f"Document record {document_id} not found")
