"""Authenticated, owner-scoped transformation history endpoints."""

from typing import List

from auth import get_current_user
from database import Database
from fastapi import APIRouter, Depends, HTTPException, Query
from models import AudioConversionResult, ConversionResult, TransformationHistoryItem

router = APIRouter(prefix="/api/history")


async def _recent(collection, user_id: str, length: int):
    cursor = collection.find({"user_id": user_id}).sort("timestamp", -1).limit(length)
    return await cursor.to_list(length=length)


@router.get("/transformations", response_model=List[TransformationHistoryItem])
async def get_transformation_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    """Return every retained transformation type as one chronological ledger."""
    db = Database.get_db()
    fetch_count = limit + offset

    documents = await _recent(db.conversions, user.id, fetch_count)
    audio = await _recent(db.audio_conversions, user.id, fetch_count)
    images = await _recent(db.image_conversions, user.id, fetch_count)
    transcriptions = await _recent(db.transcriptions, user.id, fetch_count)
    text_conversions = await _recent(db.text_conversions, user.id, fetch_count)

    items = [
        TransformationHistoryItem(
            id=item["id"],
            kind="document",
            filename=item["filename"],
            input_format="tex",
            output_format="pdf",
            success=item.get("success", False),
            timestamp=item["timestamp"],
            downloadable=item.get("success", False) and bool(item.get("pdf_path")),
        )
        for item in documents
    ]
    items.extend(
        TransformationHistoryItem(
            id=item["id"],
            kind="text",
            filename=item["filename"],
            input_format=item.get("original_format"),
            output_format=item.get("target_format", "text"),
            success=item.get("success", False),
            timestamp=item["timestamp"],
            downloadable=item.get("success", False) and bool(item.get("output_path")),
        )
        for item in text_conversions
    )
    items.extend(
        TransformationHistoryItem(
            id=item["id"],
            kind="audio",
            filename=item["filename"],
            input_format=item.get("original_format"),
            output_format=item.get("target_format", "audio"),
            success=item.get("success", False),
            timestamp=item["timestamp"],
            downloadable=item.get("success", False) and bool(item.get("audio_path")),
            detail=f"{round(item['duration'])}s" if item.get("duration") else None,
        )
        for item in audio
    )
    items.extend(
        TransformationHistoryItem(
            id=item["id"],
            kind="image",
            filename=item["filename"],
            input_format=item.get("original_format"),
            output_format=item.get("target_format", "image"),
            success=item.get("success", False),
            timestamp=item["timestamp"],
            downloadable=item.get("success", False) and bool(item.get("image_path")),
            detail=(
                f"{item['width']} x {item['height']}"
                if item.get("width") and item.get("height")
                else None
            ),
        )
        for item in images
    )
    items.extend(
        TransformationHistoryItem(
            id=item["id"],
            kind="transcript",
            filename=item["filename"],
            input_format="audio",
            output_format="text",
            success=item.get("success", False),
            timestamp=item["timestamp"],
            downloadable=False,
            retained=True,
            detail=item.get("language"),
        )
        for item in transcriptions
    )
    items.sort(key=lambda item: item.timestamp, reverse=True)
    return items[offset : offset + limit]


@router.get("/conversions", response_model=List[ConversionResult])
async def get_conversion_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    """Get conversion history for current user."""
    db = Database.get_db()
    cursor = db.conversions.find({"user_id": user.id})
    cursor = cursor.sort("timestamp", -1).skip(offset).limit(limit)
    conversions = await cursor.to_list(length=limit)
    return [ConversionResult(**conv) for conv in conversions]


@router.get("/audio-conversions", response_model=List[AudioConversionResult])
async def get_audio_conversion_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    """Get audio conversion history for current user."""
    db = Database.get_db()
    cursor = db.audio_conversions.find({"user_id": user.id})
    cursor = cursor.sort("timestamp", -1).skip(offset).limit(limit)
    conversions = await cursor.to_list(length=limit)
    return [AudioConversionResult(**conv) for conv in conversions]


@router.get("/conversions/{conversion_id}", response_model=ConversionResult)
async def get_conversion_by_id(conversion_id: str, user=Depends(get_current_user)):
    """Get specific conversion by ID."""
    db = Database.get_db()
    conversion = await db.conversions.find_one(
        {"id": conversion_id, "user_id": user.id}
    )

    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")

    return ConversionResult(**conversion)


@router.delete("/conversions/{conversion_id}")
async def delete_conversion(conversion_id: str, user=Depends(get_current_user)):
    """Delete a conversion from history."""
    db = Database.get_db()

    result = await db.conversions.delete_one({"id": conversion_id, "user_id": user.id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversion not found")

    return {"message": "Conversion deleted successfully"}
