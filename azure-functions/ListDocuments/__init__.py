import logging
import json
import azure.functions as func
import asyncio

from shared_code.database import get_database
from shared_code.models import DocumentResponse
from shared_code.auth import AuthNotConfiguredError, UnauthorizedError, get_current_user_from_request

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('List documents function triggered')

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
        # Get query parameters
        skip = int(req.params.get('skip', 0))
        limit = min(int(req.params.get('limit', 100)), 1000)  # Limit to maximum 1000 records

        user_id = user.id

        # Find documents where the user is either the owner or has permissions
        db = await get_database()
        query = {
            "$or": [
                {"uploaded_by": user_id},
                {f"permissions.{user_id}": {"$exists": True}}
            ]
        }
        
        # Execute query
        documents = []
        cursor = db.documents.find(query).skip(skip).limit(limit)
        async for doc in cursor:
            documents.append(DocumentResponse(
                id=doc["id"],
                filename=doc["filename"],
                content_type=doc["content_type"],
                size=doc["size"],
                uploaded_by=doc["uploaded_by"],
                timestamp=doc["timestamp"],
                available_permissions=["read", "write", "delete"] if doc["uploaded_by"] == user_id else 
                                      doc.get("permissions", {}).get(user_id, [])
            ).dict())
        
        return func.HttpResponse(
            json.dumps(documents, default=str),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error listing documents: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Failed to list documents: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )