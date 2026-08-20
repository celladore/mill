"""
Conversion history API endpoints.

TODO: Production enhancements:
- Add pagination
- Implement filtering and sorting
- Add search functionality
- Support for date range queries
- Add export functionality
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from auth import get_current_user
from models import ConversionResult, AudioConversionResult
from database import Database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history")


@router.get("/conversions", response_model=List[ConversionResult])
async def get_conversion_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)
):
    """Get conversion history for current user."""
    db = Database.get_db()
    
    # TODO: Filter by user_id when authentication is implemented
    # cursor = db.conversions.find({"user_id": user["id"]})
    cursor = db.conversions.find({})
    
    cursor = cursor.sort("timestamp", -1).skip(offset).limit(limit)
    
    conversions = await cursor.to_list(length=limit)
    return [ConversionResult(**conv) for conv in conversions]


@router.get("/audio-conversions", response_model=List[AudioConversionResult])
async def get_audio_conversion_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)
):
    """Get audio conversion history for current user."""
    db = Database.get_db()
    
    # TODO: Filter by user_id when authentication is implemented
    cursor = db.audio_conversions.find({})
    
    cursor = cursor.sort("timestamp", -1).skip(offset).limit(limit)
    
    conversions = await cursor.to_list(length=limit)
    return [AudioConversionResult(**conv) for conv in conversions]


@router.get("/conversions/{conversion_id}", response_model=ConversionResult)
async def get_conversion_by_id(conversion_id: str, user=Depends(get_current_user)):
    """Get specific conversion by ID."""
    db = Database.get_db()
    conversion = await db.conversions.find_one({"id": conversion_id})
    
    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    # TODO: Check user permissions
    return ConversionResult(**conversion)


@router.delete("/conversions/{conversion_id}")
async def delete_conversion(conversion_id: str, user=Depends(get_current_user)):
    """Delete a conversion from history."""
    db = Database.get_db()
    
    # TODO: Check user permissions
    result = await db.conversions.delete_one({"id": conversion_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    return {"message": "Conversion deleted successfully"}

