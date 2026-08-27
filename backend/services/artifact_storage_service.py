"""Private, durable storage for generated conversion artifacts."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

import aiofiles

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient
from config import (
    AZURE_ARTIFACT_CONTAINER,
    AZURE_STORAGE_ACCOUNT_URL,
    CONVERSION_RETENTION_SECONDS,
)
from fastapi import HTTPException

from services.azure_credential import create_storage_credential

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactMetadata:
    blob_name: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    expires_at: datetime
    created: bool = True

    def as_record(self) -> dict:
        return {
            "artifact_blob_name": self.blob_name,
            "artifact_content_type": self.content_type,
            "artifact_size_bytes": self.size_bytes,
            "artifact_sha256": self.sha256,
            "artifact_created_at": self.created_at,
            "artifact_expires_at": self.expires_at,
            "artifact_available": True,
        }


class ArtifactStorageService:
    """Store outputs under opaque, idempotent names in a private container."""

    @staticmethod
    def _container_client():
        if not AZURE_STORAGE_ACCOUNT_URL:
            raise HTTPException(
                status_code=503, detail="Artifact storage is not configured"
            )
        credential = create_storage_credential()
        service = BlobServiceClient(AZURE_STORAGE_ACCOUNT_URL, credential=credential)
        return credential, service.get_container_client(AZURE_ARTIFACT_CONTAINER)

    @staticmethod
    async def upload(
        path: Path, *, conversion_id: str, kind: str, user_id: str, content_type: str
    ) -> ArtifactMetadata:
        if not user_id:
            raise ValueError("An owner is required for every conversion artifact")

        def hash_file() -> str:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()

        size_bytes = path.stat().st_size
        digest = await asyncio.to_thread(hash_file)
        created_at = datetime.now(UTC)
        expires_at = created_at + timedelta(seconds=CONVERSION_RETENTION_SECONDS)
        blob_name = f"{kind}/{conversion_id}"
        metadata = {
            "conversion_id": conversion_id,
            "kind": kind,
            "owner_sha256": hashlib.sha256(user_id.encode()).hexdigest(),
            "sha256": digest,
            "expires_epoch": str(int(expires_at.timestamp())),
        }
        credential, container = ArtifactStorageService._container_client()
        created = True
        try:
            try:

                async def chunks():
                    async with aiofiles.open(path, "rb") as handle:
                        while chunk := await handle.read(1024 * 1024):
                            yield chunk

                await container.upload_blob(
                    name=blob_name,
                    data=chunks(),
                    length=size_bytes,
                    overwrite=False,
                    metadata=metadata,
                    content_settings=ContentSettings(content_type=content_type),
                )
            except ResourceExistsError:
                created = False
                properties = await container.get_blob_client(
                    blob_name
                ).get_blob_properties()
                if (
                    properties.size != size_bytes
                    or properties.metadata.get("sha256") != digest
                    or properties.metadata.get("owner_sha256")
                    != metadata["owner_sha256"]
                ):
                    raise RuntimeError(
                        "Existing conversion artifact does not match retry"
                    )
                created_at = properties.creation_time or created_at
                stored_expiry = properties.metadata.get("expires_epoch")
                if stored_expiry:
                    expires_at = datetime.fromtimestamp(int(stored_expiry), UTC)
        finally:
            await container.close()
            await credential.close()
        return ArtifactMetadata(
            blob_name, content_type, size_bytes, digest, created_at, expires_at, created
        )

    @staticmethod
    async def download(blob_name: str) -> AsyncIterator[bytes]:
        credential, container = ArtifactStorageService._container_client()
        try:
            stream = await container.download_blob(blob_name)
            async for chunk in stream.chunks():
                yield chunk
        finally:
            await container.close()
            await credential.close()

    @staticmethod
    async def exists(blob_name: str) -> bool:
        credential, container = ArtifactStorageService._container_client()
        try:
            try:
                await container.get_blob_client(blob_name).get_blob_properties()
                return True
            except ResourceNotFoundError:
                return False
        finally:
            await container.close()
            await credential.close()

    @staticmethod
    async def delete(blob_name: str) -> None:
        credential, container = ArtifactStorageService._container_client()
        try:
            try:
                await container.delete_blob(blob_name, delete_snapshots="include")
            except ResourceNotFoundError:
                pass
        finally:
            await container.close()
            await credential.close()

    @staticmethod
    async def delete_best_effort(blob_name: str, context: str) -> bool:
        """Rollback an orphan without hiding the error that caused the rollback."""
        try:
            await ArtifactStorageService.delete(blob_name)
            return True
        except Exception as exc:
            logger.error(
                "Could not roll back artifact %s (%s): %s", blob_name, context, exc
            )
            return False
