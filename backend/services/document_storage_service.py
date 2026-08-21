import uuid
from typing import AsyncIterator

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient
from config import (
    AZURE_CLIENT_ID,
    AZURE_STORAGE_ACCOUNT_URL,
    AZURE_STORAGE_CONTAINER,
    MAX_FILE_SIZE,
)
from fastapi import HTTPException, UploadFile

from utils.security import sanitize_filename


class DocumentStorageService:
    """Private Azure Blob storage for user-owned documents."""

    @staticmethod
    def _container_client():
        if not AZURE_STORAGE_ACCOUNT_URL:
            raise HTTPException(
                status_code=503, detail="Document storage is not configured"
            )

        credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID)
        service = BlobServiceClient(AZURE_STORAGE_ACCOUNT_URL, credential=credential)
        return credential, service.get_container_client(AZURE_STORAGE_CONTAINER)

    @staticmethod
    async def upload(user_id: str, file: UploadFile) -> tuple[str, int, str]:
        safe_filename = sanitize_filename(file.filename or "document")
        content = bytearray()

        while chunk := await file.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="File size exceeds limit")

        blob_name = f"{user_id}/{uuid.uuid4()}/{safe_filename}"
        content_type = file.content_type or "application/octet-stream"
        credential, container = DocumentStorageService._container_client()
        try:
            await container.upload_blob(
                name=blob_name,
                data=bytes(content),
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
            )
        finally:
            await container.close()
            await credential.close()

        return blob_name, len(content), content_type

    @staticmethod
    async def download(blob_name: str) -> AsyncIterator[bytes]:
        credential, container = DocumentStorageService._container_client()
        try:
            stream = await container.download_blob(blob_name)
            async for chunk in stream.chunks():
                yield chunk
        finally:
            await container.close()
            await credential.close()

    @staticmethod
    async def delete(blob_name: str) -> None:
        credential, container = DocumentStorageService._container_client()
        try:
            await container.delete_blob(blob_name, delete_snapshots="include")
        finally:
            await container.close()
            await credential.close()
