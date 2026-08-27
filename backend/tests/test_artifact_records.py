import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from azure.core.exceptions import ResourceExistsError
from fastapi import HTTPException

from services.artifact_record_service import ArtifactRecordService
from services.artifact_storage_service import ArtifactStorageService


class Collection:
    def __init__(self, records):
        self.records = records
        self.updates = []
        self.deletes = []

    async def find_one(self, query):
        return next(
            (r for r in self.records if all(r.get(k) == v for k, v in query.items())),
            None,
        )

    async def update_one(self, query, update):
        self.updates.append((query, update))
        return SimpleNamespace(modified_count=1)

    async def delete_one(self, query):
        self.deletes.append(query)
        return SimpleNamespace(deleted_count=1)


def _record(**overrides):
    record = {
        "id": "conversion-1",
        "user_id": "owner-1",
        "success": True,
        "artifact_available": True,
        "artifact_blob_name": "image/conversion-1",
        "artifact_expires_at": datetime.now(UTC) + timedelta(days=1),
    }
    record.update(overrides)
    return record


def test_download_is_owner_scoped_and_independent_of_local_files(monkeypatch):
    collection = Collection([_record()])

    async def exists(blob_name):
        return blob_name == "image/conversion-1"

    monkeypatch.setattr(
        "services.artifact_record_service.ArtifactStorageService.exists", exists
    )
    result = asyncio.run(
        ArtifactRecordService.get_download(collection, "conversion-1", "owner-1")
    )
    assert result["artifact_blob_name"] == "image/conversion-1"

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ArtifactRecordService.get_download(collection, "conversion-1", "other")
        )
    assert error.value.status_code == 404


def test_missing_lifecycle_deleted_blob_self_heals_history(monkeypatch):
    collection = Collection([_record()])

    async def missing(_blob_name):
        return False

    monkeypatch.setattr(
        "services.artifact_record_service.ArtifactStorageService.exists", missing
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ArtifactRecordService.get_download(collection, "conversion-1", "owner-1")
        )
    assert error.value.status_code == 404
    assert collection.updates[0][1]["$set"]["artifact_available"] is False


def test_user_deletion_removes_blob_before_history(monkeypatch):
    collection = Collection([_record()])
    deleted_blobs = []

    async def delete(blob_name):
        deleted_blobs.append(blob_name)

    monkeypatch.setattr(
        "services.artifact_record_service.ArtifactStorageService.delete", delete
    )
    assert asyncio.run(
        ArtifactRecordService.delete_history(collection, "conversion-1", "owner-1")
    )
    assert deleted_blobs == ["image/conversion-1"]
    assert collection.deletes == [{"id": "conversion-1", "user_id": "owner-1"}]


def test_rollback_preserves_committed_or_reused_artifacts(monkeypatch):
    deleted = []

    async def delete_best_effort(blob_name, _context):
        deleted.append(blob_name)
        return True

    monkeypatch.setattr(
        "services.artifact_record_service.ArtifactStorageService.delete_best_effort",
        delete_best_effort,
    )
    created = SimpleNamespace(blob_name="image/conversion-1", created=True)
    reused = SimpleNamespace(blob_name="image/conversion-1", created=False)

    committed = Collection([_record()])
    assert not asyncio.run(ArtifactRecordService.rollback_if_uncommitted(
        committed, created, "conversion-1", "owner-1", "ambiguous insert"
    ))
    assert not asyncio.run(ArtifactRecordService.rollback_if_uncommitted(
        Collection([]), reused, "conversion-1", "owner-1", "retry"
    ))
    assert deleted == []

    assert asyncio.run(ArtifactRecordService.rollback_if_uncommitted(
        Collection([]), created, "conversion-1", "owner-1", "failed insert"
    ))
    assert deleted == ["image/conversion-1"]


class Closable:
    async def close(self):
        pass


class ExistingBlobContainer(Closable):
    def __init__(self, *, size, sha256, owner_sha256):
        self.properties = SimpleNamespace(
            size=size,
            creation_time=datetime.now(UTC),
            metadata={
                "sha256": sha256,
                "owner_sha256": owner_sha256,
                "expires_epoch": str(
                    int((datetime.now(UTC) + timedelta(days=7)).timestamp())
                ),
            },
        )

    async def upload_blob(self, **_kwargs):
        raise ResourceExistsError("already uploaded")

    def get_blob_client(self, _blob_name):
        return self

    async def get_blob_properties(self):
        return self.properties


class CancelledCommittedBlobContainer(Closable):
    def __init__(self, *, owns_attempt=True):
        self.metadata = {}
        self.deleted = []
        self.owns_attempt = owns_attempt

    async def upload_blob(self, **kwargs):
        self.metadata = kwargs["metadata"]
        if not self.owns_attempt:
            self.metadata = {**self.metadata, "upload_attempt_id": "another-attempt"}
        raise asyncio.CancelledError

    def get_blob_client(self, _blob_name):
        return self

    async def get_blob_properties(self):
        return SimpleNamespace(metadata=self.metadata)

    async def delete_blob(self, blob_name, **_kwargs):
        self.deleted.append(blob_name)


def test_cancelled_upload_removes_blob_committed_by_same_attempt(monkeypatch, tmp_path):
    path = tmp_path / "output.bin"
    path.write_bytes(b"cancelled")
    container = CancelledCommittedBlobContainer()
    monkeypatch.setattr(
        ArtifactStorageService, "_container_client", lambda: (Closable(), container)
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            ArtifactStorageService.upload(
                path,
                conversion_id="conversion-1",
                kind="video",
                user_id="owner-1",
                content_type="video/mp4",
            )
        )

    assert container.deleted == ["video/conversion-1"]


def test_cancelled_upload_preserves_blob_from_another_attempt(monkeypatch, tmp_path):
    path = tmp_path / "output.bin"
    path.write_bytes(b"cancelled")
    container = CancelledCommittedBlobContainer(owns_attempt=False)
    monkeypatch.setattr(
        ArtifactStorageService, "_container_client", lambda: (Closable(), container)
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            ArtifactStorageService.upload(
                path,
                conversion_id="conversion-1",
                kind="video",
                user_id="owner-1",
                content_type="video/mp4",
            )
        )

    assert container.deleted == []


def test_upload_retry_is_idempotent_only_for_matching_artifact(monkeypatch, tmp_path):
    path = tmp_path / "output.bin"
    path.write_bytes(b"durable")
    import hashlib

    digest = hashlib.sha256(b"durable").hexdigest()
    owner_digest = hashlib.sha256(b"owner-1").hexdigest()
    container = ExistingBlobContainer(size=7, sha256=digest, owner_sha256=owner_digest)
    monkeypatch.setattr(
        ArtifactStorageService, "_container_client", lambda: (Closable(), container)
    )
    metadata = asyncio.run(
        ArtifactStorageService.upload(
            path,
            conversion_id="conversion-1",
            kind="image",
            user_id="owner-1",
            content_type="image/png",
        )
    )
    assert metadata.blob_name == "image/conversion-1"
    assert metadata.sha256 == digest
    assert metadata.created is False

    container.properties.size = 8
    with pytest.raises(RuntimeError, match="does not match"):
        asyncio.run(
            ArtifactStorageService.upload(
                path,
                conversion_id="conversion-1",
                kind="image",
                user_id="owner-1",
                content_type="image/png",
            )
        )
