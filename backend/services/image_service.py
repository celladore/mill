"""
Image format conversion service (JPEG/PNG/WebP/BMP/TIFF/GIF transcoding).
"""
import asyncio
import logging
import importlib.util
import os
import shutil
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiofiles

from config import CONVERSION_RETENTION_SECONDS, TEMP_DIR
from database import Database
from fastapi import HTTPException
from models import ImageConversionResult
from utils.security import sanitize_filename, validate_file_path, validate_target_format

logger = logging.getLogger(__name__)

# Kept in sync with ImageConverter.SUPPORTED_FORMATS (core/image_converter.py).
# Enforced here, before target_format is used in any path construction --
# see validate_target_format for why the converter's own format check is
# too late to serve as the sanitizer. A dict mapping each key to its own
# literal (not a set) so validate_target_format returns a hardcoded string,
# not the request's.
ALLOWED_IMAGE_FORMATS = {
    'jpeg': 'jpeg',
    'jpg': 'jpg',
    'png': 'png',
    'webp': 'webp',
    'bmp': 'bmp',
    'tiff': 'tiff',
    'gif': 'gif',
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


class ImageService:
    @staticmethod
    async def process_image_file(
        file_content: bytes,
        filename: str,
        user_id: str,
        target_format: str = 'jpeg',
        quality: str = 'high',
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
            original_format = Path(safe_filename).suffix.lower().lstrip('.')

            # Save uploaded file with safe filename (async I/O)
            input_file = temp_dir / safe_filename
            # Validate path is within temp_dir
            validate_file_path(temp_dir, input_file)
            async with aiofiles.open(input_file, 'wb') as f:
                await f.write(file_content)

            # Initialize image converter
            converter = ImageConverter()

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
                converted_path = converter.convert_image(
                    input_file,
                    output_file,
                    target_format=target_format,
                    quality=quality,
                )

                conv_success = Path(converted_path).exists()

                conv_errors = []
                conv_width = None
                conv_height = None
                if not conv_success:
                    conv_errors.append("Image conversion failed - output file not created")
                else:
                    info = converter.get_image_info(converted_path)
                    conv_width = info.get('width')
                    conv_height = info.get('height')

                # Move converted file to accessible location if successful
                conv_image_path = None
                conv_file_size_kb = None
                if conv_success:
                    final_image_filename = os.path.basename(f"{conversion_id}.{target_format}")
                    final_image_path = TEMP_DIR / final_image_filename
                    shutil.move(converted_path, final_image_path)
                    conv_image_path = str(final_image_path)
                    conv_file_size_kb = final_image_path.stat().st_size / 1024

                return (
                    conv_success, conv_errors, conv_width, conv_height,
                    conv_image_path, conv_file_size_kb,
                )

            success, errors, width, height, image_path, file_size_kb = await asyncio.to_thread(
                _convert_and_finalize
            )
            warnings = []

            # Only a file that was actually produced needs to be reclaimed;
            # a failed conversion left nothing under TEMP_DIR to expire.
            expires_at = (
                datetime.now(UTC) + timedelta(seconds=CONVERSION_RETENTION_SECONDS)
                if success else None
            )

            result_obj = ImageConversionResult(
                id=conversion_id,
                filename=Path(safe_filename).stem,
                original_format=original_format,
                target_format=target_format,
                success=success,
                errors=errors,
                warnings=warnings,
                image_path=image_path,
                file_size_kb=file_size_kb,
                width=width,
                height=height,
                user_id=user_id,
                expires_at=expires_at,
            )

            # Store result in database
            db = Database.get_db()
            await db.image_conversions.insert_one(result_obj.model_dump())

            return result_obj

        except ValueError as e:
            # Security-related errors (path traversal, invalid filename)
            logger.warning(f"Security validation error for image conversion {conversion_id}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
        except FileNotFoundError as e:
            logger.error(f"File not found error for image conversion {conversion_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=404, detail="Required file not found during processing")
        except PermissionError as e:
            logger.error(f"Permission error for image conversion {conversion_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="File system permission error")
        except Exception as e:
            # Log full exception for debugging
            logger.error(
                f"Unexpected error processing image for conversion {conversion_id}: {str(e)}",
                exc_info=True
            )
            # Don't expose internal error details to users
            raise HTTPException(
                status_code=500,
                detail="An error occurred during image processing. Please try again or contact support."
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
                        logger.error(f"Failed to clean up {temp_dir} after {max_retries} attempts: {e}")
                except Exception as e:
                    logger.error(
                        f"Error cleaning up temporary directory {temp_dir}: {e}",
                        exc_info=True
                    )
                    break
