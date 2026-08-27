"""Image format conversion service, including deterministic SVG vectorization."""

import asyncio
import importlib.util
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

import aiofiles
from config import CONVERSION_RETENTION_SECONDS, TEMP_DIR
from database import Database
from fastapi import HTTPException
from models import ImageConversionResult
from services.artifact_record_service import ArtifactRecordService
from services.artifact_storage_service import ArtifactStorageService

from utils.security import sanitize_filename, validate_file_path, validate_target_format

logger = logging.getLogger(__name__)

# Raster entries mirror ImageConverter.SUPPORTED_FORMATS; SVG uses SvgVectorizer.
# Enforced here, before target_format is used in any path construction --
# see validate_target_format for why the converter's own format check is
# too late to serve as the sanitizer. A dict mapping each key to its own
# literal (not a set) so validate_target_format returns a hardcoded string,
# not the request's.
ALLOWED_IMAGE_FORMATS = {
    "jpeg": "jpeg",
    "jpg": "jpg",
    "png": "png",
    "webp": "webp",
    "bmp": "bmp",
    "tiff": "tiff",
    "gif": "gif",
    "svg": "svg",
}

# Load only the image converter module. Importing the repository-level `core`
# package eagerly loads unrelated document converters and their optional
# dependencies, while the production image intentionally contains only this
# one module (see backend/services/audio_service.py for the same pattern).
backend_dir = Path(__file__).parent.parent
image_converter_path = backend_dir / "core" / "image_converter.py"
if not image_converter_path.exists():
    image_converter_path = backend_dir.parent / "core" / "image_converter.py"
image_converter_spec = importlib.util.spec_from_file_location(
    "xtox_image_converter", image_converter_path
)
if image_converter_spec is None or image_converter_spec.loader is None:
    raise ImportError(f"Unable to load image converter from {image_converter_path}")
image_converter_module = importlib.util.module_from_spec(image_converter_spec)
image_converter_spec.loader.exec_module(image_converter_module)
ImageConverter = image_converter_module.ImageConverter

svg_vectorizer_path = backend_dir / "core" / "svg_vectorizer.py"
if not svg_vectorizer_path.exists():
    svg_vectorizer_path = backend_dir.parent / "core" / "svg_vectorizer.py"
svg_vectorizer_spec = importlib.util.spec_from_file_location(
    "mill_svg_vectorizer", svg_vectorizer_path
)
if svg_vectorizer_spec is None or svg_vectorizer_spec.loader is None:
    raise ImportError(f"Unable to load SVG vectorizer from {svg_vectorizer_path}")
svg_vectorizer_module = importlib.util.module_from_spec(svg_vectorizer_spec)
svg_vectorizer_spec.loader.exec_module(svg_vectorizer_module)
SvgVectorizer = svg_vectorizer_module.SvgVectorizer


class ImageService:
    @staticmethod
    async def process_image_file(
        file_content: bytes,
        filename: str,
        user_id: str,
        target_format: str = "jpeg",
        quality: str = "high",
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        strip_metadata: bool = True,
        vector_colors: int = 8,
        vector_detail: int = 60,
        path_smoothing: int = 50,
        remove_background: bool = False,
        vector_max_dimension: int = 1024,
    ) -> ImageConversionResult:
        """Process image file and convert to target format"""
        conversion_id = str(uuid.uuid4())

        # Create temporary directory for this conversion
        temp_dir = TEMP_DIR / conversion_id
        temp_dir.mkdir(exist_ok=True)

        try:
            # Validate target format against an explicit allowlist before it
            # is used in any path construction below.
            target_format = validate_target_format(target_format, ALLOWED_IMAGE_FORMATS)

            # Sanitize filename to prevent path traversal
            safe_filename = sanitize_filename(filename)
            original_format = Path(safe_filename).suffix.lower().lstrip(".")

            # Save uploaded file with safe filename (async I/O)
            input_file = temp_dir / safe_filename
            # Validate path is within temp_dir
            validate_file_path(temp_dir, input_file)
            async with aiofiles.open(input_file, "wb") as f:
                await f.write(file_content)

            # Initialize image converter
            converter = ImageConverter()
            quality_value = (
                int(quality)
                if quality.isdigit()
                else converter.quality_presets[quality]
            )
            max_size = None
            if max_width or max_height:
                # A missing side remains effectively unbounded while Pillow's
                # thumbnail operation preserves the source aspect ratio.
                max_size = (max_width or 100_000, max_height or 100_000)

            # Convert image with safe filename. os.path.basename() is a
            # no-op on this value (target_format came out of an allowlist,
            # safe_stem out of sanitize_filename -- neither can contain a
            # separator) but applying it immediately before the path is
            # built keeps the sink's input unambiguously a filename, not a
            # value threaded through a few lines of intermediate string ops.
            safe_stem = Path(safe_filename).stem
            output_filename = os.path.basename(f"{safe_stem}.{target_format}")
            output_file = temp_dir / output_filename
            if output_file == input_file:
                output_file = temp_dir / f"{safe_stem}-converted.{target_format}"
            validate_file_path(temp_dir, output_file)

            def _convert_and_finalize():
                # Pillow's convert_image/get_image_info, plus the filesystem
                # move and stat below, are all synchronous and were running
                # directly on the event loop thread -- every other request
                # this worker is serving stalled behind each conversion.
                # asyncio.to_thread() below hands this whole block to a
                # worker thread; nothing in it changes vs. the prior inline
                # version, so results and error handling are unchanged.
                vector_metadata = {}
                if target_format == "svg":
                    vector_result = SvgVectorizer().vectorize(
                        input_file,
                        output_file,
                        colors=vector_colors,
                        detail=vector_detail,
                        smoothing=path_smoothing,
                        remove_background=remove_background,
                        max_dimension=vector_max_dimension,
                    )
                    converted_path = output_file
                    vector_metadata = {
                        "vector_colors": vector_result.colors,
                        "vector_paths": vector_result.paths,
                        "vector_detail": vector_detail,
                        "path_smoothing": path_smoothing,
                        "background_removed": vector_result.background_removed,
                    }
                else:
                    converted_path = converter.convert_image(
                        input_file,
                        output_file,
                        target_format=target_format,
                        quality=quality_value,
                        max_size=max_size,
                        strip_metadata=strip_metadata,
                    )

                conv_success = Path(converted_path).exists()

                conv_errors = []
                conv_width = None
                conv_height = None
                if not conv_success:
                    conv_errors.append(
                        "Image conversion failed - output file not created"
                    )
                else:
                    if target_format == "svg":
                        conv_width = vector_result.width
                        conv_height = vector_result.height
                    else:
                        info = converter.get_image_info(converted_path)
                        conv_width = info.get("width")
                        conv_height = info.get("height")

                # Keep the output in this request's temporary directory until
                # it is durably uploaded below.
                conv_image_path = None
                conv_file_size_kb = None
                if conv_success:
                    conv_image_path = str(converted_path)
                    conv_file_size_kb = Path(converted_path).stat().st_size / 1024

                return (
                    conv_success,
                    conv_errors,
                    conv_width,
                    conv_height,
                    conv_image_path,
                    conv_file_size_kb,
                    vector_metadata,
                )

            # Keep our own handle on the worker thread instead of awaiting
            # asyncio.to_thread(...) directly: if this request is cancelled,
            # asyncio.shield() lets that cancellation reach us immediately
            # while leaving convert_task running, so we can wait for it to
            # actually finish (Python threads can't be forcibly cancelled)
            # before the `finally` below is free to shutil.rmtree(temp_dir) --
            # otherwise cleanup could race a worker thread still reading or
            # writing files under temp_dir.
            convert_task = asyncio.create_task(asyncio.to_thread(_convert_and_finalize))
            try:
                (
                    success,
                    errors,
                    width,
                    height,
                    image_path,
                    file_size_kb,
                    vector_metadata,
                ) = await asyncio.shield(convert_task)
            except asyncio.CancelledError:
                try:
                    await convert_task
                except Exception:
                    pass
                raise
            warnings = []

            artifact = None
            if success and image_path:
                media_types = {
                    "jpeg": "image/jpeg",
                    "jpg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp",
                    "bmp": "image/bmp",
                    "tiff": "image/tiff",
                    "gif": "image/gif",
                    "svg": "image/svg+xml",
                }
                artifact = await ArtifactStorageService.upload(
                    Path(image_path),
                    conversion_id=conversion_id,
                    kind="image",
                    user_id=user_id,
                    content_type=media_types[target_format],
                )

            # Retain this compatibility field while artifact_expires_at is
            # the authoritative availability boundary for new records.
            expires_at = datetime.now(UTC) + timedelta(
                seconds=CONVERSION_RETENTION_SECONDS
            )

            result_obj = ImageConversionResult(
                id=conversion_id,
                filename=Path(safe_filename).stem,
                original_format=original_format,
                target_format=target_format,
                success=success,
                errors=errors,
                warnings=warnings,
                image_path=None,
                input_file_size_kb=len(file_content) / 1024,
                file_size_kb=file_size_kb,
                width=width,
                height=height,
                quality=(
                    None
                    if target_format == "svg"
                    else "custom" if quality.isdigit() else quality
                ),
                quality_value=None if target_format == "svg" else quality_value,
                max_width=max_width,
                max_height=max_height,
                metadata_stripped=strip_metadata,
                vector_colors=vector_metadata.get("vector_colors"),
                vector_paths=vector_metadata.get("vector_paths"),
                vector_detail=vector_metadata.get("vector_detail"),
                path_smoothing=vector_metadata.get("path_smoothing"),
                background_removed=vector_metadata.get("background_removed"),
                user_id=user_id,
                expires_at=expires_at,
            )

            # Store result in database
            db = Database.get_db()
            try:
                persisted = result_obj.model_dump()
                if artifact:
                    persisted.update(artifact.as_record())
                await db.image_conversions.insert_one(persisted)
            except asyncio.CancelledError:
                await ArtifactRecordService.rollback_if_uncommitted(
                    db.image_conversions,
                    artifact,
                    conversion_id,
                    user_id,
                    f"cancelled image conversion {conversion_id}",
                )
                raise
            except Exception:
                await ArtifactRecordService.rollback_if_uncommitted(
                    db.image_conversions,
                    artifact,
                    conversion_id,
                    user_id,
                    f"image conversion {conversion_id}",
                )
                raise

            return result_obj

        except HTTPException:
            raise
        except ValueError as e:
            # Security-related errors (path traversal, invalid filename)
            logger.warning(
                f"Security validation error for image conversion {conversion_id}: {str(e)}"
            )
            raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
        except FileNotFoundError as e:
            logger.error(
                f"File not found error for image conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=404, detail="Required file not found during processing"
            )
        except PermissionError as e:
            logger.error(
                f"Permission error for image conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="File system permission error")
        except Exception as e:
            # Log full exception for debugging
            logger.error(
                f"Unexpected error processing image for conversion {conversion_id}: {str(e)}",
                exc_info=True,
            )
            # Don't expose internal error details to users
            raise HTTPException(
                status_code=500,
                detail="An error occurred during image processing. Please try again or contact support.",
            )
        finally:
            # Clean up temporary directory with retry logic
            max_retries = 3
            retry_delay = 0.1

            def _remove_temp_dir():
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)

            async def _cleanup_with_retries():
                for attempt in range(max_retries):
                    try:
                        # temp_dir.exists()/shutil.rmtree() are blocking filesystem
                        # calls -- run them off the event loop so a slow disk or a
                        # permission-retry backoff can't stall other requests this
                        # worker is serving.
                        await asyncio.to_thread(_remove_temp_dir)
                        break
                    except PermissionError as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
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

            # Same shielding pattern as convert_task above: a cancellation
            # delivered while this finally block is running (e.g. a second
            # cancellation arriving mid-cleanup) must not abandon the retry
            # loop and leave temp_dir behind. asyncio.shield() lets that
            # cancellation reach us immediately while leaving cleanup_task
            # running, so we can wait for it to actually finish before the
            # cancellation is allowed to propagate further.
            cleanup_task = asyncio.create_task(_cleanup_with_retries())
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                try:
                    await cleanup_task
                except Exception:
                    pass
                raise
