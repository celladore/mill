"""
Retention sweep for converted files and their database records.

Nothing previously removed a completed image conversion's file under
TEMP_DIR or its image_conversions document -- both grew without bound.
This sweep expires each completed record together with the file it
points at, driven by the expires_at the record was written with (see
ImageService.process_image_file), rather than a MongoDB TTL index alone:
a TTL index only ever removes the Mongo document -- the file under
TEMP_DIR would keep leaking with no record left to point at it.
"""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from config import CONVERSION_RETENTION_SWEEP_INTERVAL_SECONDS
from database import Database

logger = logging.getLogger(__name__)


class RetentionService:
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
        db = Database.get_db()
        now = datetime.now(UTC)
        expired_count = 0

        cursor = db.image_conversions.find({"expires_at": {"$lte": now}})
        async for record in cursor:
            record_id = record.get("id")
            image_path = record.get("image_path")

            if image_path:
                try:
                    Path(image_path).unlink(missing_ok=True)
                except OSError as e:
                    logger.warning(
                        "Retention sweep: failed to remove file for image "
                        "conversion %s (%s): %s -- leaving record for next sweep",
                        record_id, image_path, e,
                    )
                    continue

            result = await db.image_conversions.delete_one({"id": record_id})
            if result.deleted_count:
                expired_count += 1

        if expired_count:
            logger.info("Retention sweep: expired %d image conversion(s)", expired_count)

        return expired_count

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
                await RetentionService.expire_image_conversions()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Retention sweep failed: %s", e, exc_info=True)
            await asyncio.sleep(interval)
