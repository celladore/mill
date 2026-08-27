import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from models import GenerativeTextRequest
from services import generative_text_service
from services.artifact_storage_service import ArtifactMetadata


class GeneratedTextCollection:
    def __init__(self):
        self.records = []
        self.last_query = None

    async def insert_one(self, record):
        self.records.append(record)

    async def find_one(self, query):
        self.last_query = query
        return next(
            (
                record
                for record in self.records
                if all(record.get(key) == value for key, value in query.items())
            ),
            None,
        )


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.request = httpx.Request("POST", "https://sluice.example/v1/responses")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError(
                "gateway error", request=self.request, response=response
            )

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeClient:
    def __init__(self, responses, captured):
        self.responses = iter(responses)
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, *, headers, json):
        self.captured.append((url, headers, json))
        return next(self.responses)


def _enable(monkeypatch):
    monkeypatch.setattr(generative_text_service, "GENERATIVE_TEXT_ENABLED", True)
    monkeypatch.setattr(
        generative_text_service, "SLUICE_BASE_URL", "https://sluice.example"
    )
    monkeypatch.setattr(generative_text_service, "SLUICE_API_KEY", "virtual-key")
    monkeypatch.setattr(generative_text_service, "SLUICE_TEXT_MODEL", "mill-text-v1")


def test_generation_fails_closed_while_governed_alias_is_dark(monkeypatch):
    monkeypatch.setattr(generative_text_service, "GENERATIVE_TEXT_ENABLED", False)
    request = GenerativeTextRequest(operation="generate", input="Write release notes")

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            generative_text_service.GenerativeTextService._call_sluice(
                request, "request-1"
            )
        )

    assert error.value.status_code == 503
    assert "coming soon" in error.value.detail.lower()


def test_sluice_contract_retries_429_with_one_idempotency_key(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(generative_text_service, "SLUICE_TEXT_MAX_ATTEMPTS", 3)
    captured = []
    responses = [
        FakeResponse(429, headers={"Retry-After": "0"}),
        FakeResponse(
            200,
            {"output": [{"content": [{"type": "output_text", "text": "Fresh copy"}]}]},
        ),
    ]
    monkeypatch.setattr(
        generative_text_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeClient(responses, captured),
    )

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(generative_text_service.asyncio, "sleep", no_sleep)
    request = GenerativeTextRequest(
        operation="rewrite",
        input="Original private words",
        instructions="Make it concise",
    )
    result = asyncio.run(
        generative_text_service.GenerativeTextService._call_sluice(
            request, "stable-request-id"
        )
    )

    assert generative_text_service._extract_output_text(result) == "Fresh copy"
    assert len(captured) == 2
    _, headers, payload = captured[0]
    assert headers["Idempotency-Key"] == "stable-request-id"
    assert payload["model"] == "mill-text-v1"
    assert payload["metadata"] == {
        "app": "mill",
        "agent": "generate-rewrite",
        "workflow": "rewrite",
        "stage": "production",
        "request_id": "stable-request-id",
    }
    assert captured[1][1]["Idempotency-Key"] == "stable-request-id"


@pytest.mark.parametrize("payload", [ValueError("bad json"), ["not", "an", "object"]])
def test_malformed_successful_sluice_response_becomes_502(monkeypatch, payload):
    _enable(monkeypatch)
    captured = []
    monkeypatch.setattr(
        generative_text_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeClient([FakeResponse(200, payload)], captured),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            generative_text_service.GenerativeTextService._call_sluice(
                GenerativeTextRequest(operation="generate", input="Write safely"),
                "request-1",
            )
        )

    assert error.value.status_code == 502
    assert "invalid response" in error.value.detail.lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"output": ["not-an-object"]},
        {"output": [{"content": ["not-an-object"]}]},
        {"output": {"content": []}},
        {"output": [{"content": {"text": "not-a-list"}}]},
    ],
)
def test_malformed_nested_sluice_response_becomes_502(payload):
    with pytest.raises(HTTPException) as error:
        generative_text_service._extract_output_text(payload)

    assert error.value.status_code == 502
    assert "invalid response" in error.value.detail.lower()


def test_generated_output_is_private_retained_and_prompt_is_not_persisted(
    monkeypatch, tmp_path
):
    _enable(monkeypatch)
    collection = GeneratedTextCollection()
    database = SimpleNamespace(generated_texts=collection)
    monkeypatch.setattr(generative_text_service, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(generative_text_service.Database, "get_db", lambda: database)

    async def call_sluice(_request, _request_id):
        return {
            "output_text": "# Governed output",
            "usage": {"input_tokens": 12, "output_tokens": 4, "cost": "private"},
        }

    uploaded = {}

    async def upload(path, *, conversion_id, kind, user_id, content_type):
        uploaded[conversion_id] = path.read_text("utf-8")
        now = datetime.now(UTC)
        return ArtifactMetadata(
            f"{kind}/{conversion_id}",
            content_type,
            path.stat().st_size,
            "a" * 64,
            now,
            now + timedelta(days=7),
        )

    async def exists(_blob_name):
        return True

    monkeypatch.setattr(
        generative_text_service.GenerativeTextService,
        "_call_sluice",
        call_sluice,
    )
    monkeypatch.setattr(
        generative_text_service.ArtifactStorageService, "upload", upload
    )
    monkeypatch.setattr(
        "services.artifact_record_service.ArtifactStorageService.exists", exists
    )

    result = asyncio.run(
        generative_text_service.GenerativeTextService.transform(
            GenerativeTextRequest(
                operation="generate",
                input="This prompt must not enter Mongo",
                output_format="md",
            ),
            "owner-1",
            "request-1",
        )
    )

    assert result.output_text == "# Governed output"
    assert uploaded[result.id] == "# Governed output"
    record = collection.records[0]
    assert record["user_id"] == "owner-1"
    assert record["artifact_blob_name"] == f"generation/{result.id}"
    assert "output_text" not in record
    assert "input" not in record
    assert "This prompt" not in str(record)
    assert record["usage"] == {"input_tokens": 12, "output_tokens": 4}
    blob_name, _, _ = asyncio.run(
        generative_text_service.GenerativeTextService.get_output(result.id, "owner-1")
    )
    assert collection.last_query == {"id": result.id, "user_id": "owner-1"}
    assert blob_name == f"generation/{result.id}"


def test_temp_cleanup_failure_does_not_override_committed_success(
    monkeypatch, tmp_path
):
    _enable(monkeypatch)
    collection = GeneratedTextCollection()
    database = SimpleNamespace(generated_texts=collection)
    monkeypatch.setattr(generative_text_service, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(generative_text_service.Database, "get_db", lambda: database)

    async def call_sluice(_request, _request_id):
        return {"output_text": "Committed output"}

    async def upload(path, *, conversion_id, kind, user_id, content_type):
        now = datetime.now(UTC)
        return ArtifactMetadata(
            f"{kind}/{conversion_id}",
            content_type,
            path.stat().st_size,
            "a" * 64,
            now,
            now + timedelta(days=7),
        )

    real_unlink = Path.unlink

    def fail_temp_unlink(path, *args, **kwargs):
        if path.parent == tmp_path:
            raise OSError("locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(
        generative_text_service.GenerativeTextService, "_call_sluice", call_sluice
    )
    monkeypatch.setattr(
        generative_text_service.ArtifactStorageService, "upload", upload
    )
    monkeypatch.setattr(Path, "unlink", fail_temp_unlink)

    result = asyncio.run(
        generative_text_service.GenerativeTextService.transform(
            GenerativeTextRequest(operation="generate", input="Write safely"),
            "owner-1",
        )
    )

    assert result.success is True
    assert collection.records[0]["id"] == result.id
