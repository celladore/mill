"""
API routes for document and audio conversion.

Route handlers are kept thin, delegating business logic to service layers.
This promotes separation of concerns and makes testing easier.
"""

import logging
from typing import Optional

from auth import get_current_user
from config import MAX_AUDIO_FILE_SIZE, MAX_FILE_SIZE
from dependencies import get_database
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import AudioConversionResult, ConversionResult, TranscriptionResult
from services.conversion_service import ConversionBusinessLogic
from utils.cache import cache_result
from utils.streaming import stream_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/convert", response_model=ConversionResult)
async def convert_latex_to_pdf(
    file: UploadFile = File(...),
    auto_fix: bool = False,
    user=Depends(get_current_user)
):
    """
    Convert LaTeX file to PDF.
    
    Uses streaming for large files to avoid loading entire file into memory.
    Route handler delegates business logic to ConversionBusinessLogic.
    """
    from config import TEMP_DIR
    import uuid
    import aiofiles
    
    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_upload.tex"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_FILE_SIZE)
        
        # Read and decode content from temp file
        async with aiofiles.open(temp_file, 'r', encoding='utf-8') as f:
            file_content = await f.read()
        
        # Extract filename without extension
        filename = file.filename.rsplit('.', 1)[0]
        
        # Delegate to business logic layer
        result = await ConversionBusinessLogic.convert_latex_file(
            file_content=file_content,
            filename=filename,
            auto_fix=auto_fix,
            max_file_size=MAX_FILE_SIZE
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
    user=Depends(get_current_user)
):
    """
    Download the generated PDF.
    
    Route handler uses dependency injection for database access.
    """
    # Delegate to business logic layer
    pdf_path = await ConversionBusinessLogic.get_pdf_file_path(
        conversion_id=conversion_id,
        db=db
    )
    
    # Get filename from database for response
    conversion = await db.conversions.find_one({"id": conversion_id})
    filename = conversion.get("filename", "document") if conversion else "document"
    
    return FileResponse(
        path=pdf_path,
        filename=f"{filename}.pdf",
        media_type="application/pdf"
    )


@router.get("/conversion/{conversion_id}", response_model=ConversionResult)
async def get_conversion_result(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user)
):
    """
    Get conversion result by ID.
    
    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """
    @cache_result(ttl=300, key_prefix="conversion")
    async def _get_conversion(conv_id: str, database: AsyncIOMotorDatabase):
        return await ConversionBusinessLogic.get_conversion_result(
            conversion_id=conv_id,
            db=database
        )
    
    return await _get_conversion(conversion_id, db)


@router.post("/convert-audio", response_model=AudioConversionResult)
async def convert_audio(
    file: UploadFile = File(...),
    target_format: str = Query('mp3', description="Target audio format (mp3, wav, ogg, m4a, aac, flac)"),
    bitrate: str = Query('192k', description="Audio bitrate (e.g., 128k, 192k, 320k)"),
    sample_rate: Optional[int] = Query(None, description="Sample rate in Hz (optional)"),
    user=Depends(get_current_user)
):
    """
    Convert audio file (especially WhatsApp OGG Opus) to target format.
    
    Uses streaming for large files to avoid loading entire file into memory.
    Route handler delegates business logic to ConversionBusinessLogic.
    """
    from config import TEMP_DIR
    import uuid
    import aiofiles
    
    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_audio_upload"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_AUDIO_FILE_SIZE)
        
        # Read file content from temp file
        async with aiofiles.open(temp_file, 'rb') as f:
            content = await f.read()
        
        # Delegate to business logic layer
        result = await ConversionBusinessLogic.convert_audio_file(
            file_content=content,
            filename=file.filename,
            target_format=target_format,
            bitrate=bitrate,
            sample_rate=sample_rate,
            max_file_size=MAX_AUDIO_FILE_SIZE
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
    user=Depends(get_current_user)
):
    """
    Download the converted audio file.
    
    Route handler uses dependency injection for database access.
    """
    # Delegate to business logic layer
    audio_path, media_type = await ConversionBusinessLogic.get_audio_file_path(
        conversion_id=conversion_id,
        db=db
    )
    
    # Get filename and format from database for response
    conversion = await db.audio_conversions.find_one({"id": conversion_id})
    filename = conversion.get("filename", "audio") if conversion else "audio"
    target_format = conversion.get("target_format", "mp3") if conversion else "mp3"
    
    return FileResponse(
        path=audio_path,
        filename=f"{filename}.{target_format}",
        media_type=media_type
    )


@router.get(
    "/audio-conversion/{conversion_id}",
    response_model=AudioConversionResult
)
async def get_audio_conversion_result(
    conversion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user)
):
    """
    Get audio conversion result by ID.
    
    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """
    @cache_result(ttl=300, key_prefix="audio_conversion")
    async def _get_audio_conversion(conv_id: str, database: AsyncIOMotorDatabase):
        return await ConversionBusinessLogic.get_audio_conversion_result(
            conversion_id=conv_id,
            db=database
        )

    return await _get_audio_conversion(conversion_id, db)


@router.post("/transcribe-audio", response_model=TranscriptionResult)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Query(None, description="ISO-639-1 language hint (e.g. 'en')"),
    retain: bool = Query(
        True,
        description="Persist the transcript for later retrieval. Set false for ephemeral transcription.",
    ),
    source_conversion_id: Optional[str] = Query(
        None, description="Link this transcript to an existing /convert-audio result ID"
    ),
    user=Depends(get_current_user)
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
    from config import TEMP_DIR
    import uuid
    import aiofiles

    # Create temporary file for streaming
    temp_id = str(uuid.uuid4())
    temp_file = TEMP_DIR / f"{temp_id}_transcribe_upload"
    temp_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stream file to disk (validates size during streaming)
        await stream_upload_file(file, temp_file, max_size=MAX_AUDIO_FILE_SIZE)

        # Read file content from temp file
        async with aiofiles.open(temp_file, 'rb') as f:
            content = await f.read()

        # Delegate to business logic layer
        result = await ConversionBusinessLogic.transcribe_audio_file(
            file_content=content,
            filename=file.filename,
            max_file_size=MAX_AUDIO_FILE_SIZE,
            language=language,
            source_conversion_id=source_conversion_id,
            retain=retain,
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
    user=Depends(get_current_user)
):
    """
    Get transcription result by ID.

    Results are cached for 5 minutes to reduce database load.
    Route handler uses dependency injection for database access.
    """
    @cache_result(ttl=300, key_prefix="transcription")
    async def _get_transcription(trans_id: str, database: AsyncIOMotorDatabase):
        return await ConversionBusinessLogic.get_transcription_result(
            transcription_id=trans_id,
            db=database
        )

    return await _get_transcription(transcription_id, db)
