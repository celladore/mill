"""
Speech-to-text service.

xtox does NOT call Azure OpenAI Whisper directly — that path (lib/transcription/,
a TypeScript @xtox/transcription-service package) is superseded and stays unused.
Instead, transcription is routed through sluice's OpenAI-compatible gateway:
POST {SLUICE_BASE_URL}/v1/audio/transcriptions, authenticated with a sluice
virtual key. Decision + rationale: Baton task 591273de.

That route does not exist in sluice yet (Baton task 833d6a98, blocks 591273de).
Until it ships, SluiceTranscriptionClient raises a clear 503 instead of a raw
connection error, so this endpoint is safe to deploy ahead of the dependency.
"""
import logging
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from config import (
    SLUICE_API_KEY,
    SLUICE_BASE_URL,
    SLUICE_TRANSCRIBE_TIMEOUT,
    SLUICE_TRANSCRIPTION_MODEL,
)
from database import Database
from models import TranscriptionResult

logger = logging.getLogger(__name__)


class TranscriptionService:
    @staticmethod
    async def _call_sluice(
        file_content: bytes,
        filename: str,
        language: Optional[str]
    ) -> Dict[str, Any]:
        """
        Call sluice's OpenAI/LiteLLM-compatible transcription endpoint.

        Wire contract (verified against LiteLLM docs, 2026-08-19):
          POST {SLUICE_BASE_URL}/v1/audio/transcriptions
          Authorization: Bearer <SLUICE_API_KEY>
          multipart/form-data: file=<bytes>, model=<alias>, response_format=verbose_json[, language]
          Response: at minimum {"text": ...}; verbose_json adds "language"/"duration"
          depending on the backing provider — parsed defensively below since that
          extra detail isn't guaranteed across providers.
        """
        if not SLUICE_BASE_URL or not SLUICE_API_KEY:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Transcription is not configured yet. Set SLUICE_BASE_URL and "
                    "SLUICE_API_KEY once sluice exposes POST /v1/audio/transcriptions "
                    "(tracked in Baton as 833d6a98, which blocks this feature)."
                ),
            )

        url = f"{SLUICE_BASE_URL.rstrip('/')}/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {SLUICE_API_KEY}"}
        data = {"model": SLUICE_TRANSCRIPTION_MODEL, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        files = {"file": (filename, file_content)}

        try:
            async with httpx.AsyncClient(timeout=SLUICE_TRANSCRIBE_TIMEOUT) as client:
                response = await client.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Sluice transcription gateway returned {e.response.status_code}: {e.response.text}"
            )
            raise HTTPException(
                status_code=502,
                detail=f"Transcription gateway returned an error ({e.response.status_code})",
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Sluice transcription gateway unreachable: {e}")
            raise HTTPException(status_code=502, detail="Transcription gateway is unreachable") from e

    @staticmethod
    async def transcribe_audio(
        file_content: bytes,
        filename: str,
        language: Optional[str] = None,
        source_conversion_id: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio via sluice and persist the result."""
        transcription_id = str(uuid.uuid4())

        payload = await TranscriptionService._call_sluice(file_content, filename, language)
        text = payload.get("text")

        result_obj = TranscriptionResult(
            id=transcription_id,
            filename=filename,
            success=bool(text),
            text=text,
            language=payload.get("language"),
            duration=payload.get("duration"),
            source_conversion_id=source_conversion_id,
            errors=[] if text else ["Transcription gateway returned no text"],
        )

        db = Database.get_db()
        await db.transcriptions.insert_one(result_obj.dict())

        return result_obj
