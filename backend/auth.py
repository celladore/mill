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
import os

from fastapi import Header, HTTPException

from mystira_auth import (
    AuthNotConfiguredError,
    ForbiddenError,
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


async def get_transcription_user(
    authorization: str = Header(default=None),
) -> MystiraPrincipal:
    """Authenticate direct XtOX users or explicitly scoped delegated callers.

    Delegation is limited to the transcription endpoint. Merely adding an
    audience is insufficient: delegated tokens must also carry the configured
    API-specific scope, issued and signed by the same Mystira issuer.
    """
    delegated = [
        audience.strip()
        for audience in os.environ.get("MYSTIRA_OIDC_DELEGATED_AUDIENCES", "").split(
            ","
        )
        if audience.strip()
    ]
    required_scope = os.environ.get(
        "MYSTIRA_OIDC_TRANSCRIPTION_SCOPE", "mill.transcribe"
    ).strip()

    try:
        token = extract_bearer_token(authorization)
        return validate_bearer_token(
            token,
            delegated_audiences=delegated,
            required_scope=required_scope,
        )
    except AuthNotConfiguredError as e:
        logger.error("Mystira OIDC auth not configured: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except UnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
