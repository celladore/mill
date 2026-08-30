import logging
from typing import List

from fastapi import APIRouter, HTTPException

from models import StatusCheck, StatusCheckCreate
from database import Database

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/")
async def root():
    return {"message": "Mill API - document and media conversion"}


@router.get("/health")
async def health():
    """Process liveness only; this does not assert dependency readiness."""
    return {"status": "ok", "service": "mill-api", "check": "liveness"}


@router.get("/ready")
async def ready():
    """Report readiness only after the configured MongoDB dependency responds."""
    if Database.client is None:
        raise HTTPException(status_code=503, detail="Database is not connected")
    try:
        await Database.client.admin.command("ping")
    except Exception as error:
        logger.warning("Mill readiness check failed: %s", error)
        raise HTTPException(status_code=503, detail="Database is not ready") from error
    return {"status": "ready", "service": "mill-api", "check": "readiness"}


@router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    db = Database.get_db()
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    db = Database.get_db()
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]
