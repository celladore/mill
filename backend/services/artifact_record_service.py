"""Owner-scoped artifact lookup and availability reconciliation."""

from datetime import UTC, datetime

from fastapi import HTTPException

from services.artifact_storage_service import ArtifactStorageService


class ArtifactRecordService:
    @staticmethod
    def _expired(expires_at, now: datetime) -> bool:
        if not expires_at:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= now

    @staticmethod
    async def get_download(collection, conversion_id: str, user_id: str) -> dict:
        record = await collection.find_one({"id": conversion_id, "user_id": user_id})
        if not record:
            raise HTTPException(status_code=404, detail="Conversion not found")
        if not record.get("success") or not record.get("artifact_available"):
            raise HTTPException(
                status_code=404, detail="Converted file is no longer available"
            )

        now = datetime.now(UTC)
        expires_at = record.get("artifact_expires_at")
        blob_name = record.get("artifact_blob_name")
        if not blob_name or ArtifactRecordService._expired(expires_at, now):
            if blob_name:
                await ArtifactStorageService.delete(blob_name)
            await collection.update_one(
                {"id": conversion_id, "user_id": user_id},
                {"$set": {"artifact_available": False, "artifact_deleted_at": now}},
            )
            raise HTTPException(
                status_code=404, detail="Converted file is no longer available"
            )

        if not await ArtifactStorageService.exists(blob_name):
            await collection.update_one(
                {"id": conversion_id, "user_id": user_id},
                {"$set": {"artifact_available": False, "artifact_deleted_at": now}},
            )
            raise HTTPException(
                status_code=404, detail="Converted file is no longer available"
            )
        return record

    @staticmethod
    async def delete_history(collection, conversion_id: str, user_id: str) -> bool:
        record = await collection.find_one({"id": conversion_id, "user_id": user_id})
        if not record:
            return False
        if record.get("artifact_blob_name"):
            await ArtifactStorageService.delete(record["artifact_blob_name"])
        result = await collection.delete_one({"id": conversion_id, "user_id": user_id})
        return bool(result.deleted_count)
