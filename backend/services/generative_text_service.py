"""Governed Generate / Rewrite calls routed only through Sluice."""

import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException

from config import (
    CONVERSION_RETENTION_SECONDS,
    GENERATIVE_TEXT_ENABLED,
    SLUICE_API_KEY,
    SLUICE_BASE_URL,
    SLUICE_TEXT_MAX_ATTEMPTS,
    SLUICE_TEXT_MODEL,
    SLUICE_TEXT_TIMEOUT,
    TEMP_DIR,
)
from database import Database
from models import GenerativeTextRequest, GenerativeTextResult
from services.artifact_record_service import ArtifactRecordService
from services.artifact_storage_service import ArtifactStorageService
from utils.security import validate_file_path

logger = logging.getLogger(__name__)


def _invalid_response() -> HTTPException:
    return HTTPException(
        status_code=502,
        detail="The governed text service returned an invalid response.",
    )


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    outputs = payload.get("output") or []
    if not isinstance(outputs, list):
        raise _invalid_response()
    for output in outputs:
        if not isinstance(output, dict):
            raise _invalid_response()
        contents = output.get("content") or []
        if not isinstance(contents, list):
            raise _invalid_response()
        for content in contents:
            if not isinstance(content, dict):
                raise _invalid_response()
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


class GenerativeTextService:
    @staticmethod
    def _ensure_enabled() -> None:
        if not GENERATIVE_TEXT_ENABLED or not SLUICE_BASE_URL or not SLUICE_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Generate and Rewrite are coming soon while governed AI access is enabled.",
            )

    @staticmethod
    async def _call_sluice(request: GenerativeTextRequest, request_id: str) -> dict:
        GenerativeTextService._ensure_enabled()
        instructions = (
            "Create new text from the user's brief."
            if request.operation == "generate"
            else "Rewrite the supplied text while preserving its factual meaning."
        )
        if request.instructions:
            instructions = f"{instructions}\n\nUser direction: {request.instructions}"
        payload = {
            "model": SLUICE_TEXT_MODEL,
            "instructions": instructions,
            "input": request.input,
            "max_output_tokens": request.max_output_tokens,
            "metadata": {
                "app": "mill",
                "agent": "generate-rewrite",
                "workflow": request.operation,
                "stage": "production",
                "request_id": request_id,
            },
        }
        headers = {
            "Authorization": f"Bearer {SLUICE_API_KEY}",
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            "Idempotency-Key": request_id,
        }
        url = f"{SLUICE_BASE_URL.rstrip('/')}/v1/responses"

        async with httpx.AsyncClient(timeout=SLUICE_TEXT_TIMEOUT) as client:
            for attempt in range(SLUICE_TEXT_MAX_ATTEMPTS):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        response.raise_for_status()
                        try:
                            decoded = response.json()
                        except ValueError as exc:
                            logger.warning("Sluice text response was not valid JSON")
                            raise _invalid_response() from exc
                        if not isinstance(decoded, dict):
                            logger.warning("Sluice text response was not an object")
                            raise _invalid_response()
                        return decoded
                    if attempt == SLUICE_TEXT_MAX_ATTEMPTS - 1:
                        response.raise_for_status()
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(float(retry_after), 5.0)
                    except (TypeError, ValueError):
                        delay = 0.5 * (2**attempt)
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "Sluice text request failed with status %s",
                        exc.response.status_code,
                    )
                    raise HTTPException(
                        status_code=502,
                        detail="The governed text service returned an error.",
                    ) from exc
                except httpx.RequestError as exc:
                    if attempt == SLUICE_TEXT_MAX_ATTEMPTS - 1:
                        logger.warning("Sluice text request was unreachable")
                        raise HTTPException(
                            status_code=502,
                            detail="The governed text service is temporarily unreachable.",
                        ) from exc
                    delay = 0.5 * (2**attempt)
                await asyncio.sleep(delay + random.uniform(0, 0.15))
        raise HTTPException(status_code=502, detail="The governed text service failed.")

    @staticmethod
    async def transform(
        request: GenerativeTextRequest, user_id: str, request_id: str | None = None
    ) -> GenerativeTextResult:
        conversion_id = str(uuid.uuid4())
        request_id = request_id or str(uuid.uuid4())
        payload = await GenerativeTextService._call_sluice(request, request_id)
        output = _extract_output_text(payload)
        if not output:
            raise HTTPException(
                status_code=502, detail="The governed text service returned no text."
            )

        filename = (
            "generated-text" if request.operation == "generate" else "rewritten-text"
        )
        output_path = TEMP_DIR / f"{conversion_id}.{request.output_format}"
        validate_file_path(TEMP_DIR, output_path)
        artifact = None
        try:
            await asyncio.to_thread(output_path.write_text, output, "utf-8")
            result = GenerativeTextResult(
                id=conversion_id,
                filename=filename,
                operation=request.operation,
                target_format=request.output_format,
                success=True,
                output_text=output,
                model_alias=SLUICE_TEXT_MODEL,
                usage={
                    key: int(value)
                    for key, value in (payload.get("usage") or {}).items()
                    if isinstance(value, (int, float))
                },
            )
            artifact = await ArtifactStorageService.upload(
                output_path,
                conversion_id=conversion_id,
                kind="generation",
                user_id=user_id,
                content_type=(
                    "text/markdown; charset=utf-8"
                    if request.output_format == "md"
                    else "text/plain; charset=utf-8"
                ),
            )
            persisted = result.model_dump(exclude={"output_text"})
            persisted.update(
                user_id=user_id,
                expires_at=datetime.now(UTC)
                + timedelta(seconds=CONVERSION_RETENTION_SECONDS),
            )
            persisted.update(artifact.as_record())
            await Database.get_db().generated_texts.insert_one(persisted)
            return result
        except asyncio.CancelledError:
            await ArtifactRecordService.rollback_if_uncommitted(
                Database.get_db().generated_texts,
                artifact,
                conversion_id,
                f"cancelled generative text {conversion_id}",
            )
            raise
        except Exception:
            await ArtifactRecordService.rollback_if_uncommitted(
                Database.get_db().generated_texts,
                artifact,
                conversion_id,
                f"generative text {conversion_id}",
            )
            raise
        finally:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Could not remove generated-text temp file %s", output_path
                )

    @staticmethod
    async def get_output(conversion_id: str, user_id: str):
        record = await ArtifactRecordService.get_download(
            Database.get_db().generated_texts, conversion_id, user_id
        )
        media_type = (
            "text/markdown; charset=utf-8"
            if record["target_format"] == "md"
            else "text/plain; charset=utf-8"
        )
        return record["artifact_blob_name"], media_type, record
