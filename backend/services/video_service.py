"""Bounded, deterministic FFmpeg video transcoding and metadata extraction."""

import asyncio
import json
import logging
import shutil
import uuid
from fractions import Fraction
from pathlib import Path

from config import TEMP_DIR, VIDEO_CONVERSION_TIMEOUT
from database import Database
from fastapi import HTTPException
from models import VideoConversionResult
from services.artifact_record_service import ArtifactRecordService
from services.artifact_storage_service import ArtifactStorageService
from utils.security import sanitize_filename, validate_file_path, validate_target_format

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_FORMATS = {"mp4": "mp4", "webm": "webm", "mov": "mov"}
QUALITY_CRF = {"high": 20, "balanced": 26, "small": 32}
ALLOWED_MAX_HEIGHTS = {480, 720, 1080, 1440, 2160}
MEDIA_TYPES = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}
MAX_SOURCE_PIXELS = 7680 * 4320
MAX_SOURCE_DURATION_SECONDS = 60 * 60


async def _run_process(*args: str, timeout: int) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.CancelledError:
        process.kill()
        await process.communicate()
        raise
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise HTTPException(
            status_code=408, detail="Video processing exceeded the time limit"
        )
    if process.returncode != 0:
        logger.warning("Video tool failed with exit code %s", process.returncode)
        raise HTTPException(status_code=422, detail="The video could not be processed")
    return stdout


def _frame_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        return round(float(Fraction(value)), 3)
    except (ValueError, ZeroDivisionError):
        return None


async def probe_video(path: Path) -> dict:
    payload = await _run_process(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate",
        "-of",
        "json",
        str(path),
        timeout=min(VIDEO_CONVERSION_TIMEOUT, 30),
    )
    try:
        metadata = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail="Video metadata is invalid"
        ) from exc
    streams = metadata.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if not video:
        raise HTTPException(
            status_code=422, detail="The source does not contain a video stream"
        )
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    try:
        duration = round(float((metadata.get("format") or {}).get("duration")), 3)
    except (TypeError, ValueError):
        duration = None
    return {
        "duration": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "frame_rate": _frame_rate(video.get("avg_frame_rate")),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
    }


class VideoService:
    @staticmethod
    async def process_video_file(
        input_path: Path,
        filename: str,
        target_format: str,
        quality: str,
        max_height: int | None,
        user_id: str,
    ) -> VideoConversionResult:
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        conversion_id = str(uuid.uuid4())
        temp_dir = TEMP_DIR / conversion_id
        temp_dir.mkdir(exist_ok=True)
        artifact = None
        try:
            target_format = validate_target_format(target_format, ALLOWED_VIDEO_FORMATS)
            quality = quality.lower()
            if quality not in QUALITY_CRF:
                raise HTTPException(
                    status_code=400, detail="Quality must be high, balanced, or small"
                )
            if max_height is not None and max_height not in ALLOWED_MAX_HEIGHTS:
                raise HTTPException(
                    status_code=400, detail="Unsupported maximum height"
                )

            safe_filename = sanitize_filename(filename)
            original_format = Path(safe_filename).suffix.lower().lstrip(".")
            source_metadata = await probe_video(input_path)
            source_pixels = (source_metadata.get("width") or 0) * (
                source_metadata.get("height") or 0
            )
            if source_pixels > MAX_SOURCE_PIXELS:
                raise HTTPException(
                    status_code=413, detail="Video resolution exceeds the 8K limit"
                )
            if (source_metadata.get("duration") or 0) > MAX_SOURCE_DURATION_SECONDS:
                raise HTTPException(
                    status_code=413, detail="Video duration exceeds the 60-minute limit"
                )
            output_path = temp_dir / f"{Path(safe_filename).stem}.{target_format}"
            validate_file_path(temp_dir, output_path)

            command = ["ffmpeg", "-nostdin", "-y", "-i", str(input_path)]
            if max_height:
                command.extend(["-vf", f"scale=w=-2:h='min({max_height},ih)'"])
            crf = str(QUALITY_CRF[quality])
            if target_format == "webm":
                command.extend(
                    [
                        "-c:v",
                        "libvpx-vp9",
                        "-deadline",
                        "good",
                        "-cpu-used",
                        "2",
                        "-crf",
                        crf,
                        "-b:v",
                        "0",
                        "-c:a",
                        "libopus",
                        "-b:a",
                        "128k",
                    ]
                )
            else:
                command.extend(
                    [
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",
                        "-crf",
                        crf,
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-pix_fmt",
                        "yuv420p",
                    ]
                )
                if target_format == "mp4":
                    command.extend(["-movflags", "+faststart"])
            command.append(str(output_path))
            await _run_process(*command, timeout=VIDEO_CONVERSION_TIMEOUT)

            output_metadata = await probe_video(output_path)
            artifact = await ArtifactStorageService.upload(
                output_path,
                conversion_id=conversion_id,
                kind="video",
                user_id=user_id,
                content_type=MEDIA_TYPES[target_format],
            )
            result = VideoConversionResult(
                id=conversion_id,
                filename=Path(safe_filename).stem,
                original_format=original_format,
                target_format=target_format,
                success=True,
                input_file_size_kb=input_path.stat().st_size / 1024,
                file_size_kb=output_path.stat().st_size / 1024,
                duration=output_metadata.get("duration")
                or source_metadata.get("duration"),
                width=output_metadata.get("width"),
                height=output_metadata.get("height"),
                frame_rate=output_metadata.get("frame_rate"),
                video_codec=output_metadata.get("video_codec"),
                audio_codec=output_metadata.get("audio_codec"),
                quality=quality,
                max_height=max_height,
            )
            record = result.model_dump()
            record["user_id"] = user_id
            record.update(artifact.as_record())
            db = Database.get_db()
            try:
                await db.video_conversions.insert_one(record)
            except asyncio.CancelledError:
                await ArtifactRecordService.rollback_if_uncommitted(
                    db.video_conversions,
                    artifact,
                    conversion_id,
                    user_id,
                    "cancelled video conversion",
                )
                raise
            except Exception:
                await ArtifactRecordService.rollback_if_uncommitted(
                    db.video_conversions,
                    artifact,
                    conversion_id,
                    user_id,
                    "video conversion persistence",
                )
                raise
            return result
        except HTTPException:
            raise
        except (ValueError, FileNotFoundError) as exc:
            logger.warning("Video conversion %s rejected: %s", conversion_id, exc)
            raise HTTPException(
                status_code=400, detail="Invalid video conversion request"
            ) from exc
        except Exception as exc:
            logger.error(
                "Video conversion %s failed: %s", conversion_id, exc, exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Video conversion failed"
            ) from exc
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    async def get_download(
        collection, conversion_id: str, user_id: str
    ) -> tuple[dict, str]:
        record = await ArtifactRecordService.get_download(
            collection, conversion_id, user_id
        )
        return record, MEDIA_TYPES.get(
            record.get("target_format"), "application/octet-stream"
        )
