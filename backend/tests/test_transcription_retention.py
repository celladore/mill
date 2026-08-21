import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from database import Database
from services.transcription_service import TranscriptionService


@pytest.fixture
def sluice_payload(monkeypatch):
    call = AsyncMock(return_value={"text": "hello", "language": "en", "duration": 1.25})
    monkeypatch.setattr(TranscriptionService, "_call_sluice", call)
    return call


def test_transcription_defaults_to_non_retaining_without_database_access(
    monkeypatch, sluice_payload
):
    get_db = Mock(side_effect=AssertionError("database must not be accessed"))
    monkeypatch.setattr(Database, "get_db", get_db)

    result = asyncio.run(
        TranscriptionService.transcribe_audio(
            b"audio",
            "voice.ogg",
        )
    )

    assert result.success is True
    assert result.text == "hello"
    get_db.assert_not_called()


def test_retaining_transcription_persists_result(monkeypatch, sluice_payload):
    collection = type("Collection", (), {"insert_one": AsyncMock()})()
    database = type("DatabaseStub", (), {"transcriptions": collection})()
    monkeypatch.setattr(Database, "get_db", lambda: database)

    result = asyncio.run(
        TranscriptionService.transcribe_audio(
            b"audio",
            "voice.ogg",
            source_conversion_id="conversion-1",
            retain=True,
        )
    )

    collection.insert_one.assert_awaited_once()
    persisted = collection.insert_one.await_args.args[0]
    assert persisted["id"] == result.id
    assert persisted["source_conversion_id"] == "conversion-1"
