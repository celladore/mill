"""Authenticated, durable batch conversion coordination endpoints."""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from auth import get_current_user
from capabilities import (
    BATCH_MAX_AGGREGATE_SIZE,
    BATCH_ITEM_LEASE_SECONDS,
    BATCH_MAX_ATTEMPTS,
    BATCH_MAX_ITEMS,
    BATCH_RETENTION_SECONDS,
    ROUTE_CAPABILITIES,
    public_capabilities,
)
from config import (
    MAX_AUDIO_FILE_SIZE,
    MAX_FILE_SIZE,
    MAX_IMAGE_FILE_SIZE,
    MAX_VIDEO_FILE_SIZE,
    TEMP_DIR,
)
from dependencies import get_database
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Response,
    UploadFile,
)
from models import BatchCreateRequest
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from services.conversion_service import ConversionBusinessLogic
from services.text_service import TextService
from services.video_service import VideoService
from utils.security import sanitize_filename
from utils.streaming import stream_upload_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _safe_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, HTTPException):
        return f"http_{exc.status_code}", str(exc.detail)
    logger.exception("Unexpected batch item failure")
    return "conversion_failed", "The file could not be converted."


def _item_view(item: dict, route: str) -> dict:
    item = {
        key: value
        for key, value in item.items()
        if key not in {"_id", "user_id", "result", "claim_token"}
    }
    if item.get("state") == "succeeded" and item.get("result_id"):
        endpoint = {
            "document": "download",
            "image": "download-image",
            "text": "download-text",
            "audio": "download-audio",
            "video": "download-video",
        }[route]
        item["download_url"] = f"/api/{endpoint}/{item['result_id']}"
    return item


async def _batch_view(db: AsyncIOMotorDatabase, batch: dict) -> dict:
    items = [
        item
        async for item in db.batch_items.find(
            {"batch_id": batch["id"], "user_id": batch["user_id"]}
        ).sort("position", 1)
    ]
    counts = {state: 0 for state in ("accepted", "running", "succeeded", "failed")}
    for item in items:
        counts[item["state"]] += 1
    view = {
        key: value
        for key, value in batch.items()
        if key not in {"_id", "user_id", "idempotency_hash", "request_fingerprint"}
    }
    view["items"] = [_item_view(item, batch["route"]) for item in items]
    view["counts"] = counts
    return view


async def _refresh_batch_state(
    db: AsyncIOMotorDatabase, batch_id: str, user_id: str
) -> dict:
    items = [
        item
        async for item in db.batch_items.find(
            {"batch_id": batch_id, "user_id": user_id}
        )
    ]
    states = [item["state"] for item in items]
    if any(state == "running" for state in states):
        state = "running"
    elif any(state == "accepted" for state in states):
        state = "accepted"
    elif states and all(state == "succeeded" for state in states):
        state = "succeeded"
    elif any(state == "succeeded" for state in states):
        state = "partial_success"
    else:
        state = "failed"
    update: dict[str, Any] = {"state": state, "updated_at": _now()}
    if state in {"succeeded", "partial_success", "failed"}:
        update["completed_at"] = _now()
    return await db.batches.find_one_and_update(
        {"id": batch_id, "user_id": user_id},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )


def _validate_item(route: str, filename: str, size: int) -> str:
    capability = ROUTE_CAPABILITIES[route]
    safe_name = sanitize_filename(filename)
    if not safe_name or Path(safe_name).suffix.lower() not in capability["extensions"]:
        raise HTTPException(
            status_code=400, detail=f"{filename}: unsupported file type for {route}"
        )
    if size <= 0:
        raise HTTPException(status_code=400, detail=f"{filename}: file is empty")
    if size > capability["max_file_size"]:
        raise HTTPException(
            status_code=413, detail=f"{filename}: file exceeds the route limit"
        )
    return safe_name


def _validate_settings(route: str, settings: dict) -> None:
    allowed = {
        "document": {"auto_fix"},
        "image": {
            "target_format",
            "quality",
            "max_width",
            "max_height",
            "strip_metadata",
            "vector_colors",
            "vector_detail",
            "path_smoothing",
            "remove_background",
            "vector_max_dimension",
        },
        "text": {"target_format"},
        "audio": {"target_format", "bitrate"},
        "video": {"target_format", "quality", "max_height"},
    }[route]
    unknown = set(settings) - allowed
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported batch setting: {sorted(unknown)[0]}",
        )
    target = settings.get("target_format")
    if target and str(target).lower() not in ROUTE_CAPABILITIES[route]["targets"]:
        raise HTTPException(status_code=400, detail="Unsupported target format")


def _request_fingerprint(request: BatchCreateRequest) -> str:
    payload = {
        "route": request.route,
        "settings": request.settings,
        "items": [
            {
                "filename": sanitize_filename(item.filename),
                "size": item.size,
                "sha256": item.sha256,
            }
            for item in request.items
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@router.get("/capabilities")
async def get_capabilities():
    return public_capabilities()


@router.post("/batches", status_code=202)
async def create_batch(
    request: BatchCreateRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    capability = ROUTE_CAPABILITIES.get(request.route)
    if capability is None or not capability["batch_enabled"]:
        raise HTTPException(
            status_code=400, detail="Batch conversion is not enabled for this route"
        )
    _validate_settings(request.route, request.settings)
    if not 2 <= len(request.items) <= BATCH_MAX_ITEMS:
        raise HTTPException(
            status_code=400, detail=f"A batch requires 2 to {BATCH_MAX_ITEMS} files"
        )
    normalized_names = []
    aggregate_size = 0
    for item in request.items:
        safe_name = _validate_item(request.route, item.filename, item.size)
        normalized_names.append(safe_name.casefold())
        aggregate_size += item.size
    if len(set(normalized_names)) != len(normalized_names):
        raise HTTPException(
            status_code=400, detail="Duplicate filenames are not allowed in one batch"
        )
    if aggregate_size > BATCH_MAX_AGGREGATE_SIZE:
        raise HTTPException(
            status_code=413, detail="Batch exceeds the aggregate upload limit"
        )

    idem_hash = None
    request_fingerprint = _request_fingerprint(request)
    if idempotency_key:
        if len(idempotency_key) > 200:
            raise HTTPException(status_code=400, detail="Idempotency-Key is too long")
        idem_hash = hashlib.sha256(f"{user.id}:{idempotency_key}".encode()).hexdigest()
        existing = await db.batches.find_one(
            {"user_id": user.id, "idempotency_hash": idem_hash}
        )
        if existing:
            if existing.get("request_fingerprint") != request_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used for a different batch request",
                )
            response.status_code = 200
            return await _batch_view(db, existing)

    now = _now()
    batch_id = str(uuid.uuid4())
    batch = {
        "id": batch_id,
        "user_id": user.id,
        "route": request.route,
        "settings": request.settings,
        "state": "accepted",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(seconds=BATCH_RETENTION_SECONDS),
        "request_fingerprint": request_fingerprint,
    }
    batch["idempotency_hash"] = idem_hash or f"generated:{batch_id}"
    items = [
        {
            "id": str(uuid.uuid4()),
            "batch_id": batch_id,
            "user_id": user.id,
            "position": position,
            "filename": sanitize_filename(item.filename),
            "size": item.size,
            "sha256": item.sha256,
            "state": "accepted",
            "created_at": now,
            "updated_at": now,
            "expires_at": batch["expires_at"],
            "attempts": 0,
        }
        for position, item in enumerate(request.items)
    ]
    try:
        await db.batches.insert_one(batch)
        await db.batch_items.insert_many(items)
    except DuplicateKeyError:
        await db.batch_items.delete_many({"batch_id": batch_id})
        await db.batches.delete_one({"id": batch_id})
        if idem_hash:
            existing = await db.batches.find_one(
                {"user_id": user.id, "idempotency_hash": idem_hash}
            )
            if existing:
                if existing.get("request_fingerprint") != request_fingerprint:
                    raise HTTPException(
                        status_code=409,
                        detail="Idempotency-Key was already used for a different batch request",
                    ) from None
                response.status_code = 200
                return await _batch_view(db, existing)
        raise
    except Exception:
        await db.batch_items.delete_many({"batch_id": batch_id})
        await db.batches.delete_one({"id": batch_id})
        raise
    return await _batch_view(db, batch)


@router.get("/batches")
async def list_batches(
    db: AsyncIOMotorDatabase = Depends(get_database), user=Depends(get_current_user)
):
    batches = [
        batch
        async for batch in db.batches.find({"user_id": user.id})
        .sort("created_at", -1)
        .limit(20)
    ]
    return [await _batch_view(db, batch) for batch in batches]


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    batch = await db.batches.find_one({"id": batch_id, "user_id": user.id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return await _batch_view(db, batch)


@router.get("/batches/{batch_id}/items/{item_id}")
async def get_batch_item(
    batch_id: str,
    item_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    batch = await db.batches.find_one({"id": batch_id, "user_id": user.id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch item not found")
    item = await db.batch_items.find_one(
        {"id": item_id, "batch_id": batch_id, "user_id": user.id}
    )
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found")
    return _item_view(item, batch["route"])


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _execute(
    route: str,
    file: UploadFile,
    settings: dict,
    user_id: str,
    expected_size: int,
    expected_sha256: str,
):
    safe_name = sanitize_filename(file.filename or "source")
    if route == "video":
        upload_path = (
            TEMP_DIR / f"{uuid.uuid4()}_batch_video{Path(safe_name).suffix.lower()}"
        )
        try:
            await stream_upload_file(file, upload_path, max_size=MAX_VIDEO_FILE_SIZE)
            if upload_path.stat().st_size != expected_size:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file size does not match the batch item",
                )
            actual_sha256 = await asyncio.to_thread(_sha256_path, upload_path)
            if actual_sha256 != expected_sha256:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file content does not match the batch item",
                )
            return await VideoService.process_video_file(
                upload_path,
                safe_name,
                settings.get("target_format", "mp4"),
                settings.get("quality", "balanced"),
                settings.get("max_height"),
                user_id,
            )
        finally:
            upload_path.unlink(missing_ok=True)

    content = await file.read(ROUTE_CAPABILITIES[route]["max_file_size"] + 1)
    _validate_item(route, safe_name, len(content))
    if len(content) != expected_size:
        raise HTTPException(
            status_code=400, detail="Uploaded file size does not match the batch item"
        )
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file content does not match the batch item",
        )
    if route == "document":
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="LaTeX source must be UTF-8"
            ) from exc
        return await ConversionBusinessLogic.convert_latex_file(
            decoded,
            Path(safe_name).stem,
            bool(settings.get("auto_fix", False)),
            MAX_FILE_SIZE,
            user_id,
        )
    if route == "image":
        return await ConversionBusinessLogic.convert_image_file(
            content,
            safe_name,
            user_id,
            settings.get("target_format", "webp"),
            str(settings.get("quality", "high")),
            MAX_IMAGE_FILE_SIZE,
            max_width=settings.get("max_width"),
            max_height=settings.get("max_height"),
            strip_metadata=settings.get("strip_metadata", True),
            vector_colors=settings.get("vector_colors", 8),
            vector_detail=settings.get("vector_detail", 60),
            path_smoothing=settings.get("path_smoothing", 50),
            remove_background=settings.get("remove_background", False),
            vector_max_dimension=settings.get("vector_max_dimension", 1024),
        )
    if route == "text":
        return await TextService.process_text_file(
            content, safe_name, settings.get("target_format", "html"), user_id
        )
    return await ConversionBusinessLogic.convert_audio_file(
        content,
        safe_name,
        settings.get("target_format", "mp3"),
        settings.get("bitrate", "192k"),
        None,
        MAX_AUDIO_FILE_SIZE,
        user_id,
    )


@router.post("/batches/{batch_id}/items/{item_id}/execute")
async def execute_batch_item(
    batch_id: str,
    item_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
    user=Depends(get_current_user),
):
    batch = await db.batches.find_one({"id": batch_id, "user_id": user.id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    item = await db.batch_items.find_one(
        {"id": item_id, "batch_id": batch_id, "user_id": user.id}
    )
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found")
    if item["state"] == "succeeded":
        return _item_view(item, batch["route"])
    if sanitize_filename(file.filename or "") != item["filename"]:
        raise HTTPException(
            status_code=400, detail="Uploaded filename does not match the batch item"
        )

    now = _now()
    if item["state"] == "running":
        lease_expires_at = item.get("lease_expires_at")
        if lease_expires_at and _utc(lease_expires_at) > now:
            raise HTTPException(status_code=409, detail="Batch item is already running")
        if item.get("attempts", 0) >= BATCH_MAX_ATTEMPTS:
            await db.batch_items.update_one(
                {
                    "id": item_id,
                    "user_id": user.id,
                    "state": "running",
                    "claim_token": item.get("claim_token"),
                },
                {
                    "$set": {
                        "state": "failed",
                        "claim_token": None,
                        "lease_expires_at": None,
                        "error_code": "claim_expired",
                        "error": "The conversion was interrupted too many times. Create a new batch to retry it.",
                        "completed_at": now,
                        "updated_at": now,
                    }
                },
            )
            await _refresh_batch_state(db, batch_id, user.id)
            raise HTTPException(
                status_code=409, detail="Batch item retry limit reached"
            )
        recovered = await db.batch_items.find_one_and_update(
            {
                "id": item_id,
                "batch_id": batch_id,
                "user_id": user.id,
                "state": "running",
                "claim_token": item.get("claim_token"),
            },
            {
                "$set": {
                    "state": "accepted",
                    "claim_token": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if not recovered:
            raise HTTPException(status_code=409, detail="Batch item claim changed")

    claim_token = str(uuid.uuid4())
    lease_expires_at = now + timedelta(seconds=BATCH_ITEM_LEASE_SECONDS)

    claimed = await db.batch_items.find_one_and_update(
        {"id": item_id, "batch_id": batch_id, "user_id": user.id, "state": "accepted"},
        {
            "$set": {
                "state": "running",
                "claim_token": claim_token,
                "lease_expires_at": lease_expires_at,
                "started_at": now,
                "updated_at": now,
            },
            "$inc": {"attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        raise HTTPException(
            status_code=409, detail="Batch item is already running or terminal"
        )
    await _refresh_batch_state(db, batch_id, user.id)
    try:
        result = await _execute(
            batch["route"],
            file,
            batch["settings"],
            user.id,
            item["size"],
            item["sha256"],
        )
        result_data = result.model_dump(mode="json")
        committed = await db.batch_items.update_one(
            {
                "id": item_id,
                "user_id": user.id,
                "state": "running",
                "claim_token": claim_token,
            },
            {
                "$set": {
                    "state": "succeeded",
                    "result_id": result.id,
                    "output_format": result_data.get("target_format", "pdf"),
                    "claim_token": None,
                    "lease_expires_at": None,
                    "completed_at": _now(),
                    "updated_at": _now(),
                }
            },
        )
        if committed.matched_count == 0:
            logger.warning(
                "Batch item %s lost its claim; conversion result %s is orphaned",
                item_id,
                result.id,
            )
    except asyncio.CancelledError:
        await db.batch_items.update_one(
            {
                "id": item_id,
                "user_id": user.id,
                "state": "running",
                "claim_token": claim_token,
            },
            {
                "$set": {
                    "state": "failed",
                    "claim_token": None,
                    "lease_expires_at": None,
                    "error_code": "request_cancelled",
                    "error": "The upload was interrupted. Create a new batch to retry it.",
                    "completed_at": _now(),
                    "updated_at": _now(),
                }
            },
        )
        await _refresh_batch_state(db, batch_id, user.id)
        raise
    except Exception as exc:
        code, message = _safe_error(exc)
        await db.batch_items.update_one(
            {
                "id": item_id,
                "user_id": user.id,
                "state": "running",
                "claim_token": claim_token,
            },
            {
                "$set": {
                    "state": "failed",
                    "claim_token": None,
                    "lease_expires_at": None,
                    "error_code": code,
                    "error": message,
                    "completed_at": _now(),
                    "updated_at": _now(),
                }
            },
        )
    batch = await _refresh_batch_state(db, batch_id, user.id)
    item = await db.batch_items.find_one({"id": item_id, "user_id": user.id})
    return {
        "batch": await _batch_view(db, batch),
        "item": _item_view(item, batch["route"]),
    }
