"""
FastAPI authentication dependency backed by Mystira Identity OIDC.

Validates the caller's Bearer access token against Mystira Identity's JWKS
(RS256) — see mystira_auth.py for the resource-server validation logic and
why xtox never holds a client secret. There is no mock/bypass path: if
MYSTIRA_OIDC_ISSUER/MYSTIRA_OIDC_AUDIENCE aren't configured, every protected
route fails closed with 503 rather than admitting requests. ALLOW_MOCK_AUTH
no longer exists anywhere in this codebase — for tests, override this
dependency with FastAPI's `app.dependency_overrides[get_current_user]`.
"""
import logging

from fastapi import Header, HTTPException

from mystira_auth import (
    AuthNotConfiguredError,
    MystiraPrincipal,
    UnauthorizedError,
    extract_bearer_token,
    validate_bearer_token,
)

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: str = Header(default=None),
) -> MystiraPrincipal:
    """FastAPI dependency: resolve the authenticated Mystira principal.

    Raises:
        HTTPException(503): MYSTIRA_OIDC_ISSUER/AUDIENCE not configured.
        HTTPException(401): missing/invalid/expired bearer token.
    """
    try:
        token = extract_bearer_token(authorization)
        return validate_bearer_token(token)
    except AuthNotConfiguredError as e:
        logger.error("Mystira OIDC auth not configured: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except UnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
