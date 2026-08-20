import logging
import json
import azure.functions as func
import asyncio
from io import BytesIO

from shared_code.database import get_database
from shared_code.storage import get_file
from shared_code.models import Document
from shared_code.auth import AuthNotConfiguredError, UnauthorizedError, get_current_user_from_request

async def check_document_permission(doc_id: str, user_id: str, required_permission: str = "read") -> bool:
    """Check if user has permission to access a document"""
    if not user_id:
        return False
    
    # Get document from database
    db = await get_database()
    doc = await db.documents.find_one({"id": doc_id})
    if not doc:
        return False
    
    # Document owner has all permissions
    if doc.get("uploaded_by") == user_id:
        return True
    
    # Check specific permissions
    user_permissions = doc.get("permissions", {}).get(user_id, [])
    return required_permission in user_permissions

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Document download function triggered')
    
    try:
        user = await get_current_user_from_request(req)
    except AuthNotConfiguredError as e:
        logging.error(f"Mystira OIDC auth not configured: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=503,
            mimetype="application/json"
        )
    except UnauthorizedError as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=401,
            mimetype="application/json"
        )

    try:
        # Get document ID from route parameter
        doc_id = req.route_params.get('id')
        if not doc_id:
            return func.HttpResponse(
                json.dumps({"error": "Document ID not provided"}),
                status_code=400,
                mimetype="application/json"
            )

        user_id = user.id

        # Check if user has permission to access this document
        has_permission = await check_document_permission(doc_id, user_id)
        if not has_permission:
            return func.HttpResponse(
                json.dumps({"error": "Permission denied"}),
                status_code=403,
                mimetype="application/json"
            )
        
        # Get document metadata from database
        db = await get_database()
        doc = await db.documents.find_one({"id": doc_id})
        if not doc:
            return func.HttpResponse(
                json.dumps({"error": "Document not found"}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Get file from storage
        file_content, content_type = await get_file(doc["storage_path"])
        
        # Return file content
        return func.HttpResponse(
            body=file_content,
            status_code=200,
            mimetype=doc["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename={doc['filename']}"
            }
        )
        
    except Exception as e:
        logging.error(f"Error downloading document: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Failed to download document: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )