import logging
from typing import List
from urllib.parse import quote

from auth import get_current_user
from database import Database
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from models import Document, DocumentResponse, PermissionUpdate
from services.document_storage_service import DocumentStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents")

ALLOWED_PERMISSIONS = {"read", "write", "share"}


def _response(document: dict, user_id: str) -> DocumentResponse:
    permissions = ["read", "write", "share"] if document["uploaded_by"] == user_id else (
        document.get("permissions", {}).get(user_id, [])
    )
    return DocumentResponse(**document, available_permissions=permissions)


async def _authorized_document(document_id: str, user_id: str, permission: str = "read") -> dict:
    document = await Database.get_db().documents.find_one({"id": document_id})
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document["uploaded_by"] != user_id:
        permissions = document.get("permissions", {}).get(user_id, [])
        if permission not in permissions:
            raise HTTPException(status_code=403, detail="Document access denied")
    return document


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(user=Depends(get_current_user)):
    """List documents available to the current user."""
    query = {
        "$or": [
            {"uploaded_by": user.id},
            {f"permissions.{user.id}": {"$exists": True}},
        ]
    }
    cursor = Database.get_db().documents.find(query).sort("timestamp", -1)
    return [_response(document, user.id) async for document in cursor]


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """Upload a new document."""
    blob_name, size, content_type = await DocumentStorageService.upload(user.id, file)
    document = Document(
        filename=file.filename or "document",
        content_type=content_type,
        size=size,
        blob_name=blob_name,
        uploaded_by=user.id,
    )

    try:
        await Database.get_db().documents.insert_one(document.model_dump())
    except Exception:
        await DocumentStorageService.delete(blob_name)
        raise

    return _response(document.model_dump(), user.id)


@router.get("/{document_id}/content")
async def download_document(document_id: str, user=Depends(get_current_user)):
    """Stream a document from private Blob storage after an authorization check."""
    document = await _authorized_document(document_id, user.id)
    filename = quote(document["filename"])
    return StreamingResponse(
        DocumentStorageService.download(document["blob_name"]),
        media_type=document["content_type"],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.put("/{document_id}/permissions", response_model=DocumentResponse)
async def update_permissions(
    document_id: str,
    permission_update: PermissionUpdate,
    user=Depends(get_current_user)
):
    """Update document permissions."""
    document = await _authorized_document(document_id, user.id, permission="share")
    if document["uploaded_by"] != user.id:
        raise HTTPException(status_code=403, detail="Only the document owner can share it")

    permissions = list(dict.fromkeys(permission_update.permissions))
    invalid = set(permissions) - ALLOWED_PERMISSIONS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid permissions: {', '.join(sorted(invalid))}",
        )

    if permission_update.user_id == user.id:
        raise HTTPException(status_code=400, detail="Owner permissions cannot be changed")
    if "." in permission_update.user_id or permission_update.user_id.startswith("$"):
        raise HTTPException(status_code=400, detail="Invalid user id")

    permissions_path = f"permissions.{permission_update.user_id}"
    update = {"$set": {permissions_path: permissions}} if permissions else {
        "$unset": {permissions_path: ""}
    }
    await Database.get_db().documents.update_one({"id": document_id}, update)
    document.setdefault("permissions", {})
    if permissions:
        document["permissions"][permission_update.user_id] = permissions
    else:
        document["permissions"].pop(permission_update.user_id, None)

    return _response(document, user.id)
