"""
Request handler for ConvertToAIText function.
Handles parsing requests and orchestrating the document conversion process.
"""

import logging
import json
import uuid
from typing import Tuple, Dict, Any, Optional, List

import azure.functions as func

from shared_code.models import AIConversionOptions, AIConversionResult
from shared_code.database import get_database
from shared_code.storage import store_file, get_file
from shared_code.ai.document_processor import extract_text_from_document
from shared_code.ai.text_optimizer import optimize_for_ai
from shared_code.auth import AuthNotConfiguredError, UnauthorizedError, get_current_user_from_request


class DocumentNotFoundException(Exception):
    """Raised when a document is not found"""
    pass


class PermissionDeniedException(Exception):
    """Raised when a user doesn't have permission to access a document"""
    pass


class InvalidRequestException(Exception):
    """Raised when the request is invalid or missing required data"""
    pass


async def process_request(req: func.HttpRequest) -> func.HttpResponse:
    """
    Process the AI document conversion request.
    
    Args:
        req: The HTTP request
        
    Returns:
        HTTP response with conversion result or error
    """
    try:
        user = await get_current_user_from_request(req)
    except AuthNotConfiguredError as e:
        logging.error(f"Mystira OIDC auth not configured: {e}")
        return create_error_response(str(e), 503)
    except UnauthorizedError as e:
        return create_error_response(str(e), 401)

    try:
        # Parse the request
        file_data, filename, content_type, doc_id, options = await parse_request(req)

        # If we have a document ID, fetch the document
        if doc_id:
            file_data, filename, content_type = await get_document_with_permission_check(doc_id, user.id)

        # Validate we have file data
        if not file_data:
            raise InvalidRequestException("No document provided for conversion")
        
        # Extract text from the document
        document_text = await extract_text_from_document(file_data, content_type, filename)
        
        # Optimize the text for AI consumption
        ai_text, chunks = await optimize_for_ai(document_text, options)
        
        # Create and store result
        result = await create_and_store_result(doc_id, filename, content_type, ai_text, chunks, options)
        
        # Return successful response
        return create_success_response(result)
        
    except DocumentNotFoundException:
        return create_error_response("Document not found", 404)
    except PermissionDeniedException:
        return create_error_response("Permission denied", 403)
    except InvalidRequestException as e:
        return create_error_response(str(e), 400)
    except Exception as e:
        logging.error(f"Error in AI conversion: {str(e)}", exc_info=True)
        return create_error_response(f"Failed to convert document for AI: {str(e)}", 500)


async def parse_request(req: func.HttpRequest) -> Tuple[Optional[bytes], Optional[str], Optional[str], Optional[str], AIConversionOptions]:
    """
    Parse the incoming request to extract file data, document ID, and options.
    
    Args:
        req: The HTTP request
        
    Returns:
        Tuple of (file_data, filename, content_type, doc_id, options)
    """
    file_data = None
    filename = None
    content_type = None
    doc_id = None
    options = None
    
    # Check if this is a direct file upload or a reference to an existing document
    if req.files:
        # Direct file upload
        uploaded_file = req.files.get('file')
        if uploaded_file:
            file_data = uploaded_file.read()
            filename = uploaded_file.filename
            content_type = uploaded_file.content_type
        
        # Get conversion options
        options_json = req.form.get('options')
        if options_json:
            options = AIConversionOptions(**json.loads(options_json))
        else:
            options = AIConversionOptions()
    else:
        # Check if body contains JSON with document ID
        try:
            req_body = req.get_json()
            doc_id = req_body.get('document_id')
            
            if 'options' in req_body:
                options = AIConversionOptions(**req_body['options'])
            else:
                options = AIConversionOptions()
        except:
            # Body might be a direct file upload without multipart form
            file_data = req.get_body()
            content_disposition = req.headers.get('Content-Disposition', '')
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')
            else:
                filename = f"document-{uuid.uuid4()}"
            content_type = req.headers.get('Content-Type', 'application/octet-stream')
            options = AIConversionOptions()
    
    # Set default options if not provided
    if not options:
        options = AIConversionOptions()
        
    return file_data, filename, content_type, doc_id, options


async def get_document_with_permission_check(doc_id: str, user_id: str) -> Tuple[bytes, str, str]:
    """
    Get document content with permission check.

    Args:
        doc_id: Document ID
        user_id: The authenticated caller's user ID (from get_current_user_from_request)

    Returns:
        Tuple of (file_data, filename, content_type)

    Raises:
        DocumentNotFoundException: If document doesn't exist
        PermissionDeniedException: If user doesn't have permission
    """
    # Check if user has access to this document
    db = await get_database()
    doc = await db.documents.find_one({"id": doc_id})
    
    if not doc:
        raise DocumentNotFoundException(f"Document {doc_id} not found")
    
    # Check permission (basic check - owner or has read permission)
    has_access = (doc.get("uploaded_by") == user_id or 
                  user_id in doc.get("permissions", {}) and 
                  "read" in doc.get("permissions", {}).get(user_id, []))
    
    if not has_access:
        raise PermissionDeniedException(f"User {user_id} doesn't have permission to access document {doc_id}")
    
    # Get file content from storage
    file_data, content_type = await get_file(doc["storage_path"])
    filename = doc["filename"]
    
    return file_data, filename, content_type


async def create_and_store_result(
    doc_id: Optional[str],
    filename: str,
    content_type: str,
    ai_text: str,
    chunks: List[str],
    options: AIConversionOptions
) -> AIConversionResult:
    """
    Create and store the AI conversion result.
    
    Args:
        doc_id: Document ID (if provided)
        filename: Document filename
        content_type: Document content type
        ai_text: Optimized AI text
        chunks: List of text chunks
        options: Conversion options
        
    Returns:
        The created AIConversionResult object
    """
    # Generate result ID
    result_id = str(uuid.uuid4())
    
    # Estimate token count (simple approximation)
    token_count = len(ai_text.split()) * 4 // 3  # Rough approximation
    
    # Create AI conversion result
    result = AIConversionResult(
        id=result_id,
        document_id=doc_id if doc_id else result_id,
        filename=filename,
        content_type=content_type,
        ai_text=ai_text if len(ai_text) < 1048576 else None,  # Limit size for direct response
        chunks=chunks[:10],  # Limit number of chunks in direct response
        token_count=token_count,
        model_target=options.target_model
    )
    
    # Store the full result in blob storage if it's large
    if len(ai_text) >= 1048576 or len(chunks) > 10:
        # Store the full text
        ai_text_blob_name = f"ai_conversions/{result_id}/full_text.txt"
        await store_file(ai_text.encode('utf-8'), ai_text_blob_name, "text/plain")
        result.ai_text = f"Text stored in blob: {ai_text_blob_name}"
        
        # Store each chunk
        for i, chunk in enumerate(chunks):
            chunk_blob_name = f"ai_conversions/{result_id}/chunk_{i}.txt"
            await store_file(chunk.encode('utf-8'), chunk_blob_name, "text/plain")
        
        # Update result with reference to all chunks
        result.chunks = [f"Chunk {i} stored in blob: ai_conversions/{result_id}/chunk_{i}.txt" 
                       for i in range(len(chunks))]
    
    # Store result in database
    db = await get_database()
    await db.ai_conversions.insert_one(result.dict())
    
    return result


def create_success_response(result: AIConversionResult) -> func.HttpResponse:
    """Create a successful HTTP response with the conversion result"""
    return func.HttpResponse(
        json.dumps(result.dict(), default=str),
        status_code=200,
        mimetype="application/json"
    )


def create_error_response(error_message: str, status_code: int = 400) -> func.HttpResponse:
    """Create an error HTTP response"""
    return func.HttpResponse(
        json.dumps({"error": error_message}),
        status_code=status_code,
        mimetype="application/json"
    )