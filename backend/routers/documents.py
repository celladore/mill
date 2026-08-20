import logging
from typing import List

from auth import get_current_user
from database import Database
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from models import DocumentResponse, PermissionUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents")


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(user=Depends(get_current_user)):
    """List documents available to the current user."""
    # TODO: Implement document listing
    # db = Database.get_db()
    # documents = await db.documents.find({"user_id": user["id"]})
    return []


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """Upload a new document."""
    # TODO: Implement document upload
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.put("/{document_id}/permissions", response_model=DocumentResponse)
async def update_permissions(
    document_id: str,
    permission_update: PermissionUpdate,
    user=Depends(get_current_user)
):
    """Update document permissions."""
    # TODO: Implement permission updates
    raise HTTPException(status_code=501, detail="Not yet implemented")