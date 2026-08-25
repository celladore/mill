"""
Business logic for conversion operations.

Separates business logic from HTTP route handlers, making the code
more testable and maintainable.

TODO: Production enhancements:
- Add transaction support for multi-step operations
- Implement retry logic for transient failures
- Add operation logging and metrics
- Support for batch operations
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from models import (
    AudioConversionResult,
    ConversionResult,
    ImageConversionResult,
    TranscriptionResult,
)
from services.audio_service import AudioService
from services.image_service import ImageService
from services.latex_service import LatexService
from services.transcription_service import TranscriptionService
from utils.file_validator import FileValidator

logger = logging.getLogger(__name__)


class ConversionBusinessLogic:
    """Business logic layer for conversion operations."""
    
    @staticmethod
    async def convert_latex_file(
        file_content: str,
        filename: str,
        auto_fix: bool,
        max_file_size: int
    ) -> ConversionResult:
        """
        Convert LaTeX file to PDF.
        
        Args:
            file_content: Content of the LaTeX file
            filename: Name of the file (without extension)
            auto_fix: Whether to auto-fix common LaTeX errors
            max_file_size: Maximum allowed file size
        
        Returns:
            ConversionResult: Result of the conversion
        
        Raises:
            HTTPException: If validation fails or conversion error occurs
        """
        # Validate file
        file_size = len(file_content.encode('utf-8'))
        is_valid, error_message = FileValidator.validate_latex_file(
            f"{filename}.tex", file_size, max_file_size
        )
        if not is_valid:
            status_code = 400 if 'size' not in error_message.lower() else 413
            raise HTTPException(status_code=status_code, detail=error_message)
        
        # Process conversion
        try:
            result = await LatexService.process_latex_file(
                file_content, filename, auto_fix
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error converting LaTeX: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An error occurred during conversion"
            ) from e
    
    @staticmethod
    async def get_conversion_result(
        conversion_id: str,
        db: AsyncIOMotorDatabase
    ) -> ConversionResult:
        """
        Get conversion result by ID.
        
        Args:
            conversion_id: ID of the conversion
            db: Database instance
        
        Returns:
            ConversionResult: Conversion result
        
        Raises:
            HTTPException: If conversion not found
        """
        conversion = await db.conversions.find_one({"id": conversion_id})
        if not conversion:
            raise HTTPException(
                status_code=404,
                detail="Conversion not found"
            )
        return ConversionResult(**conversion)
    
    @staticmethod
    async def get_pdf_file_path(
        conversion_id: str,
        db: AsyncIOMotorDatabase
    ) -> Path:
        """
        Get PDF file path for download.
        
        Args:
            conversion_id: ID of the conversion
            db: Database instance
        
        Returns:
            Path: Path to the PDF file
        
        Raises:
            HTTPException: If conversion not found or PDF unavailable
        """
        conversion = await db.conversions.find_one({"id": conversion_id})
        if not conversion:
            raise HTTPException(
                status_code=404,
                detail="Conversion not found"
            )
        
        if not conversion.get("success") or not conversion.get("pdf_path"):
            raise HTTPException(
                status_code=400,
                detail="PDF not available for this conversion"
            )
        
        pdf_path = Path(conversion["pdf_path"])
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail="PDF file not found"
            )
        
        return pdf_path
    
    @staticmethod
    async def convert_audio_file(
        file_content: bytes,
        filename: str,
        target_format: str,
        bitrate: str,
        sample_rate: Optional[int],
        max_file_size: int
    ) -> AudioConversionResult:
        """
        Convert audio file to target format.
        
        Args:
            file_content: Binary content of the audio file
            filename: Name of the file
            target_format: Target format (mp3, wav, etc.)
            bitrate: Audio bitrate
            sample_rate: Optional sample rate
            max_file_size: Maximum allowed file size
        
        Returns:
            AudioConversionResult: Result of the conversion
        
        Raises:
            HTTPException: If validation fails or conversion error occurs
        """
        # Validate file size
        file_size = len(file_content)
        is_valid, error_message = FileValidator.validate_audio_file(
            filename, file_size, max_file_size
        )
        if not is_valid:
            status_code = 400 if 'size' not in error_message.lower() else 413
            raise HTTPException(status_code=status_code, detail=error_message)
        
        # Validate target format
        valid_formats = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'}
        if target_format.lower() not in valid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target format. Supported formats: {', '.join(valid_formats)}"
            )
        
        # Process conversion
        try:
            result = await AudioService.process_audio_file(
                file_content,
                filename,
                target_format=target_format.lower(),
                bitrate=bitrate,
                sample_rate=sample_rate
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error converting audio: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An error occurred during audio conversion"
            ) from e
    
    @staticmethod
    async def get_audio_conversion_result(
        conversion_id: str,
        db: AsyncIOMotorDatabase
    ) -> AudioConversionResult:
        """
        Get audio conversion result by ID.
        
        Args:
            conversion_id: ID of the conversion
            db: Database instance
        
        Returns:
            AudioConversionResult: Conversion result
        
        Raises:
            HTTPException: If conversion not found
        """
        conversion = await db.audio_conversions.find_one({"id": conversion_id})
        if not conversion:
            raise HTTPException(
                status_code=404,
                detail="Audio conversion not found"
            )
        return AudioConversionResult(**conversion)
    
    @staticmethod
    async def get_audio_file_path(
        conversion_id: str,
        db: AsyncIOMotorDatabase
    ) -> tuple[Path, str]:
        """
        Get audio file path and media type for download.
        
        Args:
            conversion_id: ID of the conversion
            db: Database instance
        
        Returns:
            tuple[Path, str]: Path to audio file and media type
        
        Raises:
            HTTPException: If conversion not found or audio unavailable
        """
        conversion = await db.audio_conversions.find_one({"id": conversion_id})
        if not conversion:
            raise HTTPException(
                status_code=404,
                detail="Audio conversion not found"
            )
        
        if not conversion.get("success") or not conversion.get("audio_path"):
            raise HTTPException(
                status_code=400,
                detail="Converted audio not available"
            )
        
        audio_path = Path(conversion["audio_path"])
        if not audio_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Audio file not found"
            )
        
        # Determine media type
        format_to_media_type = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'm4a': 'audio/mp4',
            'aac': 'audio/aac',
            'flac': 'audio/flac'
        }
        target_format = conversion.get("target_format", "mp3")
        media_type = format_to_media_type.get(target_format, 'audio/mpeg')

        return audio_path, media_type

    @staticmethod
    async def transcribe_audio_file(
        file_content: bytes,
        filename: str,
        max_file_size: int,
        language: Optional[str] = None,
        source_conversion_id: Optional[str] = None,
        retain: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file to text via sluice's gateway.

        Args:
            file_content: Binary content of the audio file
            filename: Name of the file
            max_file_size: Maximum allowed file size
            language: Optional ISO-639-1 language hint
            source_conversion_id: Optional id of a prior /convert-audio result to link to
            retain: Whether to persist the transcript for later retrieval

        Returns:
            TranscriptionResult: Result of the transcription

        Raises:
            HTTPException: If validation fails, the gateway isn't configured (503),
                the gateway errors (502), or an unexpected error occurs (500)
        """
        # Validate file (same allowlist/size rules as /convert-audio)
        file_size = len(file_content)
        is_valid, error_message = FileValidator.validate_audio_file(
            filename, file_size, max_file_size
        )
        if not is_valid:
            status_code = 400 if 'size' not in error_message.lower() else 413
            raise HTTPException(status_code=status_code, detail=error_message)

        try:
            result = await TranscriptionService.transcribe_audio(
                file_content,
                filename,
                language=language,
                source_conversion_id=source_conversion_id,
                retain=retain,
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error transcribing audio: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An error occurred during transcription"
            ) from e

    @staticmethod
    async def get_transcription_result(
        transcription_id: str,
        db: AsyncIOMotorDatabase
    ) -> TranscriptionResult:
        """
        Get transcription result by ID.

        Args:
            transcription_id: ID of the transcription
            db: Database instance

        Returns:
            TranscriptionResult: Transcription result

        Raises:
            HTTPException: If transcription not found
        """
        transcription = await db.transcriptions.find_one({"id": transcription_id})
        if not transcription:
            raise HTTPException(
                status_code=404,
                detail="Transcription not found"
            )
        return TranscriptionResult(**transcription)

    @staticmethod
    async def convert_image_file(
        file_content: bytes,
        filename: str,
        target_format: str,
        quality: str,
        max_file_size: int
    ) -> ImageConversionResult:
        """
        Convert image file to target format.

        Args:
            file_content: Binary content of the image file
            filename: Name of the file
            target_format: Target format (jpeg, png, webp, bmp, tiff, gif)
            quality: Quality preset (high, medium, low, web)
            max_file_size: Maximum allowed file size

        Returns:
            ImageConversionResult: Result of the conversion

        Raises:
            HTTPException: If validation fails or conversion error occurs
        """
        # Validate file size and extension
        file_size = len(file_content)
        is_valid, error_message = FileValidator.validate_image_file(
            filename, file_size, max_file_size
        )
        if not is_valid:
            status_code = 400 if 'size' not in error_message.lower() else 413
            raise HTTPException(status_code=status_code, detail=error_message)

        # Validate target format
        valid_formats = {'jpeg', 'jpg', 'png', 'webp', 'bmp', 'tiff', 'gif'}
        if target_format.lower() not in valid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target format. Supported formats: {', '.join(sorted(valid_formats))}"
            )

        # Process conversion
        try:
            result = await ImageService.process_image_file(
                file_content,
                filename,
                target_format=target_format.lower(),
                quality=quality.lower(),
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error converting image: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An error occurred during image conversion"
            ) from e

    @staticmethod
    async def get_image_conversion_result(
        conversion_id: str,
        db: AsyncIOMotorDatabase
    ) -> ImageConversionResult:
        """
        Get image conversion result by ID.

        Args:
            conversion_id: ID of the conversion
            db: Database instance

        Returns:
            ImageConversionResult: Conversion result

        Raises:
            HTTPException: If conversion not found
        """
        conversion = await db.image_conversions.find_one({"id": conversion_id})
        if not conversion:
            raise HTTPException(
                status_code=404,
                detail="Image conversion not found"
            )
        return ImageConversionResult(**conversion)

    @staticmethod
    async def get_image_file_path(
        conversion_id: str,
        db: AsyncIOMotorDatabase
    ) -> tuple[Path, str]:
        """
        Get image file path and media type for download.

        Args:
            conversion_id: ID of the conversion
            db: Database instance

        Returns:
            tuple[Path, str]: Path to image file and media type

        Raises:
            HTTPException: If conversion not found or image unavailable
        """
        conversion = await db.image_conversions.find_one({"id": conversion_id})
        if not conversion:
            raise HTTPException(
                status_code=404,
                detail="Image conversion not found"
            )

        if not conversion.get("success") or not conversion.get("image_path"):
            raise HTTPException(
                status_code=400,
                detail="Converted image not available"
            )

        image_path = Path(conversion["image_path"])
        if not image_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Image file not found"
            )

        # Determine media type
        format_to_media_type = {
            'jpeg': 'image/jpeg',
            'jpg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff',
            'gif': 'image/gif'
        }
        target_format = conversion.get("target_format", "jpeg")
        media_type = format_to_media_type.get(target_format, 'application/octet-stream')

        return image_path, media_type

