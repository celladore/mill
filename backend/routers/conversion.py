"""
API routes for document and audio conversion.

Route handlers are kept thin, delegating business logic to service layers.
This promotes separation of concerns and makes testing easier.
"""

import logging
from typing import Optional

from auth import get_current_user, get_transcription_user
from config import MAX_AUDIO_FILE_SIZE, MAX_FILE_SIZE, MAX_IMAGE_FILE_SIZE
from dependencies import get_database
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from models import (
    AudioConversionResult,
    ConversionResult,
    ImageConversionResult,
    TextConversionResult,
    TranscriptionResult,
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.conversion_service import ConversionBusinessLogic
from services.text_service import TextService

from utils.cache import cache_result
from utils.streaming import stream_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/convert-text", response_model=TextConversionResult)
async def convert_text(
    file: UploadFile = File(...),
    target_format: str = Query(
        "html", description="Target format: md, html, txt, or docx"
    ),
    user=Depends(get_current_user),
):
    """Convert between supported deterministic text formats."""
    import uuid

    import aiofiles
    from config import TEMP_DIR

    temp_file = TEMP_DIR / f"{uuid.uuid4()}_text_upload"
    try:
        await stream_upload_file(file, temp_file, max_size=MAX_FILE_SIZE)
        async with aiofiles.open(temp_file, "rb") as handle:
            content = await handle.read()
        return await TextService.process_text_file(
            content, file.filename, target_format, user.id
        )
    finally:
        try:
            temp_file.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove text upload %s: %s", temp_file, exc)


@router.get("/download-text/{conversion_id}")
async def download_text(conversion_id: str, user=Depends(get_current_user)):
    path, media_type, record = await TextService.get_output(conversion_id, user.id)
    return FileResponse(
        path=path,
        filename=f"{record['filename']}.{record['target_format']}",
        media_type=media_type,
    )


@router.post("/convert", response_model=ConversionResult)
async def convert_latex_to_pdf(
    file: UploadFile = File(...), auto_fix: bool = False, user=Depends(get_current_user)
):
    """
    Convert LaTeX file to PDF.

    Uses streaming for large files to avoid loading entire file into memory.
    Route handler delegates business logic to ConversionBusinessLogic.
    """
    import uuid

    import aiofiles
    from config import TEMP_DIR

    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_upload.tex"
    temp_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_FILE_SIZE)

        # Read and decode content from temp file
        async with aiofiles.open(temp_file, "r", encoding="utf-8") as f:
            file_content = await f.read()

        # Extract filename without extension
        filename = file.filename.rsplit(".", 1)[0]

        # Delegate to business logic layer
        result = await ConversionBusinessLogic.convert_latex_file(
            file_content=file_content,
            filename=filename,
            auto_fix=auto_fix,
            max_file_size=MAX_FILE_SIZE,
            user_id=user.id,
        )

        return result
    finally:
        # Clean up temp file
        try:
            import aiofiles.os

            if await aiofiles.os.path.exists(temp_file):
                await aiofiles.os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {temp_file}: {e}")


@router.get("/download/{conversion_id}")
async def download_pdf(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Download the generated PDF.

    Route handler uses dependency injection for database access.
    """
    # Delegate to business logic layer
    pdf_path = await ConversionBusinessLogic.get_pdf_file_path(
        conversion_id=conversion_id,
        db=db,
        user_id=user.id,
    )

    # Get filename from database for response
    conversion = await db.conversions.find_one(
        {"id": conversion_id, "user_id": user.id}
    )
    filename = conversion.get("filename", "document") if conversion else "document"

    return FileResponse(
        path=pdf_path, filename=f"{filename}.pdf", media_type="application/pdf"
    )


@router.get("/conversion/{conversion_id}", response_model=ConversionResult)
async def get_conversion_result(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Get conversion result by ID.

    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """

    @cache_result(ttl=300, key_prefix="conversion")
    async def _get_conversion(
        conv_id: str, requester_id: str, database: AsyncIOMotorDatabase
    ):
        return await ConversionBusinessLogic.get_conversion_result(
            conversion_id=conv_id,
            db=database,
            user_id=requester_id,
        )

    return await _get_conversion(conversion_id, user.id, db)


@router.post("/convert-audio", response_model=AudioConversionResult)
async def convert_audio(
    file: UploadFile = File(...),
    target_format: str = Query(
        "mp3", description="Target audio format (mp3, wav, ogg, m4a, aac, flac)"
    ),
    bitrate: str = Query("192k", description="Audio bitrate (e.g., 128k, 192k, 320k)"),
    sample_rate: Optional[int] = Query(
        None, description="Sample rate in Hz (optional)"
    ),
    user=Depends(get_current_user),
):
    """
    Convert audio file (especially WhatsApp OGG Opus) to target format.

    Uses streaming for large files to avoid loading entire file into memory.
    Route handler delegates business logic to ConversionBusinessLogic.
    """
    import uuid

    import aiofiles
    from config import TEMP_DIR

    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_audio_upload"
    temp_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_AUDIO_FILE_SIZE)

        # Read file content from temp file
        async with aiofiles.open(temp_file, "rb") as f:
            content = await f.read()

        # Delegate to business logic layer
        result = await ConversionBusinessLogic.convert_audio_file(
            file_content=content,
            filename=file.filename,
            target_format=target_format,
            bitrate=bitrate,
            sample_rate=sample_rate,
            max_file_size=MAX_AUDIO_FILE_SIZE,
            user_id=user.id,
        )

        return result
    finally:
        # Clean up temp file
        try:
            import aiofiles.os

            if await aiofiles.os.path.exists(temp_file):
                await aiofiles.os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {temp_file}: {e}")


@router.get("/download-audio/{conversion_id}")
async def download_audio(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Download the converted audio file.

    Route handler uses dependency injection for database access.
    """
    # Delegate to business logic layer
    audio_path, media_type = await ConversionBusinessLogic.get_audio_file_path(
        conversion_id=conversion_id,
        db=db,
        user_id=user.id,
    )

    # Get filename and format from database for response
    conversion = await db.audio_conversions.find_one(
        {"id": conversion_id, "user_id": user.id}
    )
    filename = conversion.get("filename", "audio") if conversion else "audio"
    target_format = conversion.get("target_format", "mp3") if conversion else "mp3"

    return FileResponse(
        path=audio_path, filename=f"{filename}.{target_format}", media_type=media_type
    )


@router.get("/audio-conversion/{conversion_id}", response_model=AudioConversionResult)
async def get_audio_conversion_result(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Get audio conversion result by ID.

    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """

    @cache_result(ttl=300, key_prefix="audio_conversion")
    async def _get_audio_conversion(
        conv_id: str, requester_id: str, database: AsyncIOMotorDatabase
    ):
        return await ConversionBusinessLogic.get_audio_conversion_result(
            conversion_id=conv_id,
            db=database,
            user_id=requester_id,
        )

    return await _get_audio_conversion(conversion_id, user.id, db)


@router.post("/transcribe-audio", response_model=TranscriptionResult)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Query(
        None, description="ISO-639-1 language hint (e.g. 'en')"
    ),
    retain: bool = Query(
        False,
        description=(
            "Persist the transcript for later retrieval. "
            "Defaults to ephemeral transcription."
        ),
    ),
    source_conversion_id: Optional[str] = Query(
        None, description="Link this transcript to an existing /convert-audio result ID"
    ),
    user=Depends(get_transcription_user),
):
    """
    Transcribe an audio file (WhatsApp OGG/Opus voice notes, WAV, MP3, ...) to text.

    Routed through sluice's OpenAI-compatible gateway (POST /v1/audio/transcriptions)
    rather than calling Azure OpenAI Whisper directly. Returns 503 if sluice hasn't
    exposed that route yet (tracked in Baton as 833d6a98, which blocks this feature
    from working end-to-end).

    Uses streaming for large files to avoid loading entire file into memory.
    Route handler delegates business logic to ConversionBusinessLogic.
    """
    import uuid

    import aiofiles
    from config import TEMP_DIR

    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_transcribe_upload"
    temp_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_AUDIO_FILE_SIZE)

        # Read file content from temp file
        async with aiofiles.open(temp_file, "rb") as f:
            content = await f.read()

        # Delegate to business logic layer
        result = await ConversionBusinessLogic.transcribe_audio_file(
            file_content=content,
            filename=file.filename,
            max_file_size=MAX_AUDIO_FILE_SIZE,
            language=language,
            source_conversion_id=source_conversion_id,
            retain=retain,
            user_id=user.id,
        )

        return result
    finally:
        # Clean up temp file
        try:
            import aiofiles.os

            if await aiofiles.os.path.exists(temp_file):
                await aiofiles.os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {temp_file}: {e}")


@router.get("/transcription/{transcription_id}", response_model=TranscriptionResult)
async def get_transcription_result(
    transcription_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Get transcription result by ID.

    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """

    @cache_result(ttl=300, key_prefix="transcription")
    async def _get_transcription(
        trans_id: str, requester_id: str, database: AsyncIOMotorDatabase
    ):
        return await ConversionBusinessLogic.get_transcription_result(
            transcription_id=trans_id,
            db=database,
            user_id=requester_id,
        )

    return await _get_transcription(transcription_id, user.id, db)


@router.post("/convert-image", response_model=ImageConversionResult)
async def convert_image(
    file: UploadFile = File(...),
    target_format: str = Query(
        "jpeg", description="Target image format (jpeg, png, webp, bmp, tiff, gif)"
    ),
    quality: str = Query("high", description="Quality preset (high, medium, low, web)"),
    max_width: Optional[int] = Query(None, ge=1, le=16384),
    max_height: Optional[int] = Query(None, ge=1, le=16384),
    strip_metadata: bool = Query(
        True, description="Remove EXIF and embedded color-profile metadata"
    ),
    user=Depends(get_current_user),
):
    """
    Convert image file (JPEG, PNG, WebP, BMP, TIFF, GIF) to a target format.

    Uses streaming for large files to avoid loading entire file into memory.
    Route handler delegates business logic to ConversionBusinessLogic.
    """
    import uuid

    import aiofiles
    from config import TEMP_DIR

    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_image_upload"
    temp_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_IMAGE_FILE_SIZE)

        # Read file content from temp file
        async with aiofiles.open(temp_file, "rb") as f:
            content = await f.read()

        # Delegate to business logic layer
        result = await ConversionBusinessLogic.convert_image_file(
            file_content=content,
            filename=file.filename,
            user_id=user.id,
            target_format=target_format,
            quality=quality,
            max_file_size=MAX_IMAGE_FILE_SIZE,
            max_width=max_width,
            max_height=max_height,
            strip_metadata=strip_metadata,
        )

        return result
    finally:
        # Clean up temp file
        try:
            import aiofiles.os

            if await aiofiles.os.path.exists(temp_file):
                await aiofiles.os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {temp_file}: {e}")


@router.get("/download-image/{conversion_id}")
async def download_image(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Download the converted image file.

    Route handler uses dependency injection for database access.
    """
    # Delegate to business logic layer
    image_path, media_type = await ConversionBusinessLogic.get_image_file_path(
        conversion_id=conversion_id, user_id=user.id, db=db
    )

    # Get filename and format from database for response
    conversion = await db.image_conversions.find_one(
        {"id": conversion_id, "user_id": user.id}
    )
    filename = conversion.get("filename", "image") if conversion else "image"
    target_format = conversion.get("target_format", "jpeg") if conversion else "jpeg"

    return FileResponse(
        path=image_path, filename=f"{filename}.{target_format}", media_type=media_type
    )


@router.get("/image-conversion/{conversion_id}", response_model=ImageConversionResult)
async def get_image_conversion_result(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    """
    Get image conversion result by ID.

    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """

    @cache_result(ttl=300, key_prefix="image_conversion")
    async def _get_image_conversion(
        conv_id: str, requester_id: str, database: AsyncIOMotorDatabase
    ):
        return await ConversionBusinessLogic.get_image_conversion_result(
            conversion_id=conv_id, user_id=requester_id, db=database
        )

    return await _get_image_conversion(conversion_id, user.id, db)
