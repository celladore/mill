"""
Authentication and authorization module for xtotext (azure-functions runtime).

Token validation against Mystira Identity OIDC (RS256/JWKS, resource-server
side) lives in mystira_auth.py — this module wires that into the
request/User/permission model used by the rest of the azure-functions app.
There is no mock/bypass path: ALLOW_MOCK_AUTH and the local HS256
JWT_SECRET_KEY path have both been removed. A missing/invalid/expired token
is always rejected; missing MYSTIRA_OIDC_ISSUER/AUDIENCE config is rejected
too (503-equivalent, via AuthNotConfiguredError), never treated as "auth off".
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
import azure.functions as func

from .database import get_database
from .models import User, Permission, Document
from .mystira_auth import (
    AuthError,
    AuthNotConfiguredError,
    UnauthorizedError,
    extract_bearer_token,
    validate_bearer_token,
)

__all__ = [
    "AuthError",
    "AuthNotConfiguredError",
    "UnauthorizedError",
    "ForbiddenError",
    "get_current_user_from_request",
    "check_document_permission",
    "check_permission_or_raise",
]


class ForbiddenError(AuthError):
    """Raised when a user doesn't have required permissions"""
    pass


async def get_current_user_from_request(req: func.HttpRequest) -> User:
    """
    Extract and validate the current user from the request.

    Validates the caller's Bearer token against Mystira Identity's JWKS
    (RS256) — see mystira_auth.py — then hydrates the local User record
    keyed on the token's `sub` claim.

    Args:
        req: The HTTP request

    Returns:
        The authenticated user

    Raises:
        AuthNotConfiguredError: MYSTIRA_OIDC_ISSUER/AUDIENCE aren't configured.
        UnauthorizedError: missing/invalid/expired token, or the token's
            subject has no corresponding local user record.
    """
    token = extract_bearer_token(req.headers.get('Authorization'))
    principal = validate_bearer_token(token)  # raises AuthNotConfiguredError / UnauthorizedError

    db = await get_database()
    user_data = await db.users.find_one({"id": principal.id})

    if not user_data:
        raise UnauthorizedError("User not found")

    # Update last login time
    await db.users.update_one(
        {"id": principal.id},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    return User(**user_data)


async def check_document_permission(
    user_id: str,
    document_id: str,
    required_action: str
) -> bool:
    """
    Check if a user has permission to perform an action on a document.

    Args:
        user_id: The user ID
        document_id: The document ID
        required_action: The action to check ("read", "write", "delete", "share")

    Returns:
        True if the user has permission, False otherwise
    """
    try:
        # Get document from database
        db = await get_database()
        doc = await db.documents.find_one({"id": document_id})

        if not doc:
            logging.warning(f"Document {document_id} not found during permission check")
            return False

        # Convert to Document model for easier access
        document = Document(**doc)

        # Check if user is the owner
        if document.uploaded_by == user_id:
            return True

        # Check explicit permissions
        user_permissions = document.permissions.get(user_id, [])
        if required_action in user_permissions:
            return True

        # Check for admin role (has access to all documents)
        user_data = await db.users.find_one({"id": user_id})
        if user_data and "admin" in user_data.get("roles", []):
            return True

        return False

    except Exception as e:
        logging.error(f"Error checking document permission: {str(e)}")
        return False


async def check_permission_or_raise(
    user_id: str,
    document_id: str,
    required_action: str
) -> None:
    """
    Check document permission and raise error if not allowed.

    Args:
        user_id: The user ID
        document_id: The document ID
        required_action: The action to check

    Raises:
        ForbiddenError: If the user doesn't have permission
    """
    has_permission = await check_document_permission(user_id, document_id, required_action)

    if not has_permission:
        raise ForbiddenError(
            f"User {user_id} doesn't have {required_action} permission for document {document_id}"
        )
