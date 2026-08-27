"""Expire private blobs while preserving transformation history metadata."""

import asyncio
import logging
from datetime import UTC, datetime
from config import CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS
from database import Database
from services.artifact_storage_service import ArtifactStorageService

logger = logging.getLogger(__name__)


class RetentionService:
    @staticmethod
    async def _expire_collection(collection_name: str, path_field: str = "") -> int:
        db = Database.get_db()
        collection = getattr(db, collection_name)
        now = datetime.now(UTC)
        expired_count = 0
        cursor = collection.find(
            {
                "artifact_available": True,
                "artifact_expires_at": {"$lte": now},
            }
        )
        async for record in cursor:
            record_id = record.get("id")
            blob_name = record.get("artifact_blob_name")
            if blob_name:
                try:
                    await ArtifactStorageService.delete(blob_name)
                except Exception as exc:
                    logger.warning(
                        "Retention sweep could not remove %s for %s: %s",
                        blob_name,
                        record_id,
                        exc,
                    )
                    continue
            result = await collection.update_one(
                {"id": record_id, "artifact_available": True},
                {"$set": {"artifact_available": False, "artifact_deleted_at": now}},
            )
            expired_count += int(bool(result.modified_count))
        return expired_count

    @staticmethod
    async def expire_image_conversions() -> int:
        """
        Delete every image_conversions record whose expires_at has passed,
        together with the file it points at.

        Missing files and records are handled gracefully:
        - A record with no file (failed conversion, or the file was already
          removed) still has its record deleted.
        - A file removal failure for any other reason (e.g. permissions)
          leaves the record in place for the next sweep, rather than
          deleting the DB record while the file leaks.
        - A record deleted between the query and the delete (a concurrent
          sweep on another replica) is simply not counted; it isn't an
          error.

        Returns:
            Number of records expired this sweep.
        """
        return await RetentionService._expire_collection("image_conversions")

    @staticmethod
    async def expire_text_conversions() -> int:
        """Expire deterministic text outputs together with their metadata."""
        return await RetentionService._expire_collection("text_conversions")

    @staticmethod
    async def expire_all() -> int:
        return sum(
            [
                await RetentionService._expire_collection(name)
                for name in (
                    "conversions",
                    "audio_conversions",
                    "video_conversions",
                    "image_conversions",
                    "text_conversions",
                    "generated_texts",
                )
            ]
        )

    @staticmethod
    async def run_forever(interval_seconds: int = None) -> None:
        """
        Run the retention sweep on a fixed interval until cancelled.

        Launched as a background asyncio task from the app's startup hook
        (see server.py) and cancelled on shutdown. A failed sweep is logged
        and swallowed, not raised -- a transient DB hiccup shouldn't kill
        the loop; the next interval tries again.
        """
        interval = interval_seconds or CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS
        while True:
            try:
                await RetentionService.expire_all()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Retention sweep failed: %s", e, exc_info=True)
            await asyncio.sleep(interval)
