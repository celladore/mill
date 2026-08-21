"""
Regression tests for the transcribe-audio logging constraint.

Baton task 0de04c4f requires that this path never log audio, filenames,
transcript text, bearer tokens, or provider response bodies. The
non-retaining transcription mode itself already shipped in commit
871dafb; these tests cover two logging leaks found on that same path:

  * services/transcription_service.py logged the raw sluice gateway
    response body on HTTP errors.
  * utils/streaming.py logged the original uploaded filename.
"""
import asyncio
import logging
from io import BytesIO

import httpx
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from services.transcription_service import TranscriptionService
from utils.streaming import stream_upload_file


def test_sluice_error_log_never_contains_response_body(monkeypatch, caplog):
    """The provider's error response body must never be written to logs."""
    secret_body = "SECRET_BODY_SENTINEL_provider_error_detail"

    monkeypatch.setattr(
        "services.transcription_service.SLUICE_BASE_URL", "https://sluice.example"
    )
    monkeypatch.setattr(
        "services.transcription_service.SLUICE_API_KEY", "test-secret-key"
    )

    request = httpx.Request("POST", "https://sluice.example/v1/audio/transcriptions")
    response = httpx.Response(502, content=secret_body.encode(), request=request)

    async def fake_post(self, url, headers=None, data=None, files=None):
        return response

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException):
            asyncio.run(
                TranscriptionService._call_sluice(b"audio-bytes", "voice.ogg", None)
            )

    assert secret_body not in caplog.text
    # Status code stays — it's the useful, non-sensitive part of the error.
    assert "502" in caplog.text


def test_stream_upload_file_log_never_contains_filename(tmp_path, caplog):
    """The user-supplied filename must never be written to logs."""
    secret_filename = "SECRET_FILENAME_SENTINEL_voice_note.m4a"
    upload = UploadFile(filename=secret_filename, file=BytesIO(b"fake audio bytes"))
    destination = tmp_path / "generated-temp-id_transcribe_upload"

    with caplog.at_level(logging.INFO):
        asyncio.run(stream_upload_file(upload, destination))

    assert secret_filename not in caplog.text
    # The generated destination path (not derived from the filename) is fine to log.
    assert str(destination) in caplog.text
