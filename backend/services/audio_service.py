"""
Audio format conversion service (transcoding only — see transcription_service.py
for speech-to-text).
"""
import logging
import importlib.util
import shutil
import time
import uuid
from pathlib import Path

import aiofiles

from config import TEMP_DIR
from database import Database
from fastapi import HTTPException
from models import AudioConversionResult
from utils.security import sanitize_filename, validate_file_path

logger = logging.getLogger(__name__)

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
        target_format: str = 'mp3',
        bitrate: str = '192k',
        sample_rate: int = None
    ) -> AudioConversionResult:
        """Process audio file and convert to target format"""
        conversion_id = str(uuid.uuid4())

        # Create temporary directory for this conversion
        temp_dir = TEMP_DIR / conversion_id
        temp_dir.mkdir(exist_ok=True)

        try:
            # Sanitize filename to prevent path traversal
            safe_filename = sanitize_filename(filename)
            original_format = Path(safe_filename).suffix.lower().lstrip('.')

            # Save uploaded file with safe filename (async I/O)
            input_file = temp_dir / safe_filename
            # Validate path is within temp_dir
            validate_file_path(temp_dir, input_file)
            # POC: Using aiofiles for async file I/O. For production, consider
            # streaming for very large audio files.
            async with aiofiles.open(input_file, 'wb') as f:
                await f.write(file_content)

            # Initialize audio converter
            converter = AudioConverter()

            # Get audio info before conversion
            audio_info = converter.get_audio_info(input_file)
            duration = audio_info.get('duration')

            # Convert audio with safe filename
            safe_stem = Path(safe_filename).stem
            output_filename = f"{safe_stem}.{target_format}"
            output_file = temp_dir / output_filename
            validate_file_path(temp_dir, output_file)

            converted_path = converter.convert_audio(
                input_file,
                output_file,
                target_format=target_format,
                bitrate=bitrate,
                sample_rate=sample_rate
            )

            success = Path(converted_path).exists()

            errors = []
            warnings = []

            if not success:
                errors.append("Audio conversion failed - output file not created")

            # Move converted file to accessible location if successful
            audio_path = None
            file_size_kb = None
            if success:
                final_audio_path = TEMP_DIR / f"{conversion_id}.{target_format}"
                shutil.move(converted_path, final_audio_path)
                audio_path = str(final_audio_path)
                file_size_kb = final_audio_path.stat().st_size / 1024

            result_obj = AudioConversionResult(
                id=conversion_id,
                filename=Path(safe_filename).stem,
                original_format=original_format,
                target_format=target_format,
                success=success,
                errors=errors,
                warnings=warnings,
                audio_path=audio_path,
                file_size_kb=file_size_kb,
                duration=duration
            )

            # Store result in database
            db = Database.get_db()
            await db.audio_conversions.insert_one(result_obj.model_dump())

            return result_obj

        except ValueError as e:
            # Security-related errors (path traversal, invalid filename)
            logger.warning(f"Security validation error for audio conversion {conversion_id}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
        except FileNotFoundError as e:
            logger.error(f"File not found error for audio conversion {conversion_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=404, detail="Required file not found during processing")
        except PermissionError as e:
            logger.error(f"Permission error for audio conversion {conversion_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="File system permission error")
        except Exception as e:
            # Log full exception for debugging
            logger.error(
                f"Unexpected error processing audio for conversion {conversion_id}: {str(e)}",
                exc_info=True
            )
            # Don't expose internal error details to users
            raise HTTPException(
                status_code=500,
                detail="An error occurred during audio processing. Please try again or contact support."
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
