"""Azure Blob Storage adapter for document management.

Supports large-file chunked uploads, SAS-URL generation, and listing
with prefix filtering.  Authentication uses ``DefaultAzureCredential``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContainerClient,
    generate_blob_sas,
)

logger = structlog.get_logger()

# Default chunk size for large uploads: 4 MiB
_DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024


class BlobStorageAdapter:
    """Async-style adapter for Azure Blob Storage.

    Parameters
    ----------
    account_url:
        Storage account URL, e.g.
        ``https://myaccount.blob.core.windows.net``.
    container_name:
        Name of the blob container.
    credential:
        Azure credential instance.  Defaults to ``DefaultAzureCredential``.
    chunk_size:
        Chunk size in bytes for staged/block uploads.
    """

    def __init__(
        self,
        account_url: str,
        container_name: str,
        *,
        credential: DefaultAzureCredential | None = None,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> None:
        self._account_url = account_url
        self._container_name = container_name
        self._credential = credential or DefaultAzureCredential()
        self._chunk_size = chunk_size

        self._service_client = BlobServiceClient(
            account_url=account_url,
            credential=self._credential,
        )
        self._container_client: ContainerClient = self._service_client.get_container_client(container_name)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        blob_name: str,
        data: bytes | str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        """Upload a document to blob storage.

        For files larger than ``chunk_size`` the SDK automatically uses
        block-blob staged upload.
        """
        blob_client = self._container_client.get_blob_client(blob_name)
        upload_data = data.encode("utf-8") if isinstance(data, str) else data

        blob_client.upload_blob(
            upload_data,
            blob_type="BlockBlob",
            content_settings={"content_type": content_type} if content_type else None,
            metadata=metadata,
            overwrite=overwrite,
            max_concurrency=4,
            max_single_put_size=self._chunk_size,
        )

        props = blob_client.get_blob_properties()
        logger.info(
            "blob_storage.uploaded",
            blob=blob_name,
            size=props.size,
            content_type=content_type,
        )
        return {
            "blob_name": blob_name,
            "size": props.size,
            "etag": props.etag,
            "last_modified": props.last_modified.isoformat() if props.last_modified else None,
            "content_type": content_type,
        }

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    async def download_document(self, blob_name: str) -> bytes:
        """Download a document as raw bytes."""
        blob_client = self._container_client.get_blob_client(blob_name)
        stream = blob_client.download_blob()
        content = stream.readall()
        logger.debug("blob_storage.downloaded", blob=blob_name, size=len(content))
        return content

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_documents(
        self,
        *,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List blobs in the container with optional prefix filtering."""
        blobs = self._container_client.list_blobs(name_starts_with=prefix)
        results: list[dict[str, Any]] = []
        for blob in blobs:
            results.append(
                {
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None,
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "metadata": blob.metadata,
                }
            )
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # SAS URL
    # ------------------------------------------------------------------

    async def get_document_url(
        self,
        blob_name: str,
        *,
        expiry_hours: int = 1,
        permissions: str = "r",
    ) -> str:
        """Generate a time-limited SAS URL for a blob.

        Parameters
        ----------
        blob_name:
            Name of the blob.
        expiry_hours:
            Hours until the SAS token expires.
        permissions:
            SAS permission string (default ``"r"`` = read).
        """
        delegation_key = self._service_client.get_user_delegation_key(
            key_start_time=datetime.now(UTC),
            key_expiry_time=datetime.now(UTC) + timedelta(hours=expiry_hours),
        )

        sas_token = generate_blob_sas(
            account_name=self._service_client.account_name,
            container_name=self._container_name,
            blob_name=blob_name,
            user_delegation_key=delegation_key,
            permission=BlobSasPermissions(read="r" in permissions, write="w" in permissions),
            expiry=datetime.now(UTC) + timedelta(hours=expiry_hours),
        )
        url = f"{self._account_url}/{self._container_name}/{blob_name}?{sas_token}"
        logger.debug("blob_storage.sas_generated", blob=blob_name, expiry_hours=expiry_hours)
        return url

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_document(self, blob_name: str) -> None:
        """Delete a blob from the container."""
        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.delete_blob()
        logger.info("blob_storage.deleted", blob=blob_name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the service client."""
        self._service_client.close()
        logger.info("blob_storage.closed")
