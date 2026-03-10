"""Document upload/download API endpoints."""

import structlog
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from openinsure.infrastructure.factory import get_blob_storage

router = APIRouter()
logger = structlog.get_logger()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    submission_id: str | None = Query(None),
    policy_id: str | None = Query(None),
    claim_id: str | None = Query(None),
    document_type: str = Query("other"),
) -> dict[str, object]:
    """Upload a document to Azure Blob Storage."""
    storage = get_blob_storage()
    if not storage:
        # In-memory fallback
        return {
            "filename": file.filename,
            "size": 0,
            "storage": "memory",
            "url": f"/documents/{file.filename}",
            "message": "Document received (in-memory mode — not persisted)",
        }

    # Build blob path: documents/{type}/{entity_id}/{filename}
    entity_id = submission_id or policy_id or claim_id or "unattached"
    blob_name = f"{document_type}/{entity_id}/{file.filename}"

    content = await file.read()
    result = await storage.upload_document(
        blob_name=blob_name,
        data=content,
        content_type=file.content_type or "application/octet-stream",
        metadata={
            "submission_id": submission_id or "",
            "policy_id": policy_id or "",
            "claim_id": claim_id or "",
            "document_type": document_type,
            "original_filename": file.filename or "",
        },
    )

    return {
        "filename": file.filename,
        "blob_name": blob_name,
        "size": len(content),
        "storage": "azure",
        "url": result.get("url", ""),
        "etag": result.get("etag", ""),
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
    storage = get_blob_storage()
    if not storage:
        raise HTTPException(404, "Document storage not configured")

    try:
        url = await storage.get_document_url(blob_name, expiry_hours=1)
        return {"blob_name": blob_name, "download_url": url}
    except Exception as e:
        raise HTTPException(404, f"Document not found: {e}")
