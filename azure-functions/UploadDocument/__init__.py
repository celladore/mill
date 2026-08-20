import logging
import json
import azure.functions as func
import asyncio
import uuid
import os
from io import BytesIO

from shared_code.database import get_database
from shared_code.storage import store_file
from shared_code.models import Document, DocumentResponse
from shared_code.auth import AuthNotConfiguredError, UnauthorizedError, get_current_user_from_request

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Document upload function triggered')

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
        # Check if there's a file in the request
        file_data = None
        filename = None
        content_type = None
        
        # Check for multipart form data
        if req.files:
            uploaded_file = req.files.get('file')
            if uploaded_file:
                file_data = uploaded_file.read()
                filename = uploaded_file.filename
                content_type = uploaded_file.content_type
        
        # Check for binary request body if no multipart form
        if not file_data and req.get_body():
            file_data = req.get_body()
            # Try to get filename from headers
            content_disposition = req.headers.get('Content-Disposition', '')
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')
            else:
                filename = f"document-{uuid.uuid4()}"
            
            # Try to get content type from headers
            content_type = req.headers.get('Content-Type', 'application/octet-stream')
        
        if not file_data:
            return func.HttpResponse(
                json.dumps({"error": "No file provided in the request"}),
                status_code=400,
                mimetype="application/json"
            )
        
        user_id = user.id

        # Generate document ID
        doc_id = str(uuid.uuid4())
        
        # Store file in Azure Blob Storage
        blob_name = f"documents/{doc_id}/{filename}"
        storage_path = await store_file(file_data, blob_name, content_type)
        
        # Create document entry
        doc = Document(
            id=doc_id,
            filename=filename,
            content_type=content_type,
            size=len(file_data),
            storage_path=storage_path,
            storage_type="azure_blob",
            uploaded_by=user_id
        )
        
        # Store metadata in MongoDB
        db = await get_database()
        await db.documents.insert_one(doc.dict())
        
        # Return response
        response = DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            content_type=doc.content_type,
            size=doc.size,
            uploaded_by=doc.uploaded_by,
            timestamp=doc.timestamp,
            available_permissions=["read", "write", "delete"]
        )
        
        return func.HttpResponse(
            json.dumps(response.dict(), default=str),
            status_code=201,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error uploading document: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Failed to upload document: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )