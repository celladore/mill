"""
Audio format conversion service (transcoding only — see transcription_service.py
for speech-to-text).
"""

import logging
import importlib.util
import os
import shutil
import time
import uuid
from pathlib import Path

import aiofiles

from config import TEMP_DIR
from database import Database
from fastapi import HTTPException
from models import AudioConversionResult
from utils.security import sanitize_filename, validate_file_path, validate_target_format
from services.artifact_storage_service import ArtifactStorageService

logger = logging.getLogger(__name__)

# Kept in sync with AudioConverter.SUPPORTED_OUTPUT_FORMATS (core/audio_converter.py).
# Enforced here, before target_format is used in any path construction --
# see validate_target_format for why the converter's own format check is
# too late to serve as the sanitizer. A dict mapping each key to its own
# literal (not a set) so validate_target_format returns a hardcoded string,
# not the request's.
ALLOWED_AUDIO_FORMATS = {
    "mp3": "mp3",
    "wav": "wav",
    "ogg": "ogg",
    "m4a": "m4a",
    "aac": "aac",
    "flac": "flac",
}

# Load only the audio converter module. Importing the repository-level `core`
# package eagerly loads unrelated document converters and their optional
# dependencies, while the production image intentionally contains only this
# one module.
backend_dir = Path(__file__).parent.parent
audio_converter_path = backend_dir / "core" / "audio_converter.py"
if not audio_converter_path.exists():
    audio_converter_path = backend_dir.parent / "core" / "audio_converter.py"
audio_converter_spec = importlib.util.spec_from_file_location(
    "xtox_audio_converter", audio_converter_path
)
if audio_converter_spec is None or audio_converter_spec.loader is None:
    raise ImportError(f"Unable to load audio converter from {audio_converter_path}")
audio_converter_module = importlib.util.module_from_spec(audio_converter_spec)
audio_converter_spec.loader.exec_module(audio_converter_module)
AudioConverter = audio_converter_module.AudioConverter


class AudioService:
    @staticmethod
    async def process_audio_file(
        file_content: bytes,
        filename: str,
        target_format: str = "mp3",
        bitrate: str = "192k",
        sample_rate: int = None,
        user_id: str | None = None,
    ) -> AudioConversionResult:
        """Process audio file and convert to target format"""
        conversion_id = str(uuid.uuid4())

        # Create temporary directory for this conversion
        temp_dir = TEMP_DIR / conversion_id
        temp_dir.mkdir(exist_ok=True)

        try:
            # Validate target format against an explicit allowlist before it
            # is used in any path construction below.
            target_format = validate_target_format(target_format, ALLOWED_AUDIO_FORMATS)

            # Sanitize filename to prevent path traversal
            safe_filename = sanitize_filename(filename)
            original_format = Path(safe_filename).suffix.lower().lstrip(".")

            # Save uploaded file with safe filename (async I/O)
            input_file = temp_dir / safe_filename
            # Validate path is within temp_dir
            validate_file_path(temp_dir, input_file)
            # POC: Using aiofiles for async file I/O. For production, consider
            # streaming for very large audio files.
            async with aiofiles.open(input_file, "wb") as f:
                await f.write(file_content)

            # Initialize audio converter
            converter = AudioConverter()

            # Get audio info before conversion
            audio_info = converter.get_audio_info(input_file)
            duration = audio_info.get("duration")

            # Convert audio with safe filename. os.path.basename() is a
            # no-op on this value (target_format came out of an allowlist,
            # safe_stem out of sanitize_filename -- neither can contain a
            # separator) but applying it immediately before the path is
            # built keeps the sink's input unambiguously a filename.
            safe_stem = Path(safe_filename).stem
            output_filename = os.path.basename(f"{safe_stem}.{target_format}")
            output_file = temp_dir / output_filename
            validate_file_path(temp_dir, output_file)

            converted_path = converter.convert_audio(
                input_file,
                output_file,
                target_format=target_format,
                bitrate=bitrate,
                sample_rate=sample_rate,
            )

            success = Path(converted_path).exists()

            errors = []
            warnings = []

            if not success:
                errors.append("Audio conversion failed - output file not created")

            artifact = None
            file_size_kb = None
            if success:
                converted_file = Path(converted_path)
                file_size_kb = converted_file.stat().st_size / 1024
                media_types = {
                    "mp3": "audio/mpeg",
                    "wav": "audio/wav",
                    "ogg": "audio/ogg",
                    "m4a": "audio/mp4",
                    "aac": "audio/aac",
                    "flac": "audio/flac",
                }
                artifact = await ArtifactStorageService.upload(
                    converted_file,
                    conversion_id=conversion_id,
                    kind="audio",
                    user_id=user_id or "",
                    content_type=media_types[target_format],
                )

            result_obj = AudioConversionResult(
                id=conversion_id,
                filename=Path(safe_filename).stem,
                original_format=original_format,
                target_format=target_format,
                success=success,
                errors=errors,
                warnings=warnings,
                audio_path=None,
                file_size_kb=file_size_kb,
                duration=duration,
            )

            # Store result in database
            db = Database.get_db()
            persisted_result = result_obj.model_dump()
            if user_id:
                persisted_result["user_id"] = user_id
            if artifact:
                persisted_result.update(artifact.as_record())
            try:
                await db.audio_conversions.insert_one(persisted_result)
            except Exception:
                if artifact:
                    await ArtifactStorageService.delete_best_effort(
                        artifact.blob_name, f"audio conversion {conversion_id}"
                    )
                raise

            return result_obj

        except ValueError as e:
            # Security-related errors (path traversal, invalid filename)
            logger.warning(
                f"Security validation error for audio conversion {conversion_id}: {str(e)}"
            )
            raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
        except FileNotFoundError as e:
            logger.error(
                f"File not found error for audio conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=404, detail="Required file not found during processing"
            )
        except PermissionError as e:
            logger.error(
                f"Permission error for audio conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="File system permission error")
        except Exception as e:
            # Log full exception for debugging
            logger.error(
                f"Unexpected error processing audio for conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            # Don't expose internal error details to users
            raise HTTPException(
                status_code=500,
                detail="An error occurred during audio processing. Please try again or contact support.",
            )
        finally:
            # Clean up temporary directory with retry logic
            max_retries = 3
            retry_delay = 0.1

            for attempt in range(max_retries):
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir)
                    break
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} cleaning up {temp_dir}: {e}"
                        )
                    else:
                        logger.error(
                            f"Failed to clean up {temp_dir} after {max_retries} attempts: {e}"
                        )
                except Exception as e:
                    logger.error(
                        f"Error cleaning up temporary directory {temp_dir}: {e}",
                        exc_info=True,
                    )
                    break
