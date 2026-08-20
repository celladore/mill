"""
Mystira Identity OIDC resource-server token validation.

xtox is a headless API — it validates Bearer access tokens already issued by
Mystira Identity's OpenIddict authorization server. It does NOT perform the
interactive authorization_code+PKCE login handshake itself; that belongs to
whichever client actually signs the user in (the not-yet-built xtox
Convert/Transcribe frontend, proposed in mystira-workspace as the
`celladore-xtox` OIDC client — Public + PKCE, no client secret held by a
server. That's why xtox never needs MYSTIRA_OIDC_CLIENT_SECRET or a Key Vault
entry for one, unlike house-of-veritas's confidential-RP setup.)

STATUS (2026-08-20): `celladore-xtox` only exists in a Draft ADR addendum
(docs/architecture/adr/0029-addendum-02-celladore-org-rps.md, branch
docs/adr-0029-addendum-02-celladore-org-rps in mystira-workspace) — guardian
review, mason review, and project-owner sign-off are all unchecked, and that
addendum's own text states "no client row above may be seeded against any
environment until [it] is Accepted." That means no real
MYSTIRA_OIDC_ISSUER/MYSTIRA_OIDC_AUDIENCE value exists yet for any
environment, dev included. Both MUST stay unset (see backend/config.py)
until the addendum is accepted and the actual audience value the IdP will
issue is confirmed. Missing config fails CLOSED (503 via
AuthNotConfiguredError) — it never falls back to a bypass.

This module is intentionally duplicated in
azure-functions/shared_code/mystira_auth.py: the two runtimes deploy
independently (the Function App zip only ever contains azure-functions/) and
no shared pip-installable package exists across them yet. Keep both copies
in sync by hand; do not let them drift.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

_DISCOVERY_CACHE_TTL_SECONDS = 3600
_lock = threading.Lock()
_discovery_cache: Dict[str, Tuple[float, str]] = {}  # issuer -> (fetched_at, jwks_uri)
_jwks_clients: Dict[str, PyJWKClient] = {}  # jwks_uri -> client


class AuthError(Exception):
    """Base class for authentication errors."""


class UnauthorizedError(AuthError):
    """A request had no valid Mystira-issued access token."""


class AuthNotConfiguredError(AuthError):
    """MYSTIRA_OIDC_ISSUER / MYSTIRA_OIDC_AUDIENCE aren't set.

    Kept distinct from UnauthorizedError so logs/alerts can tell "this
    deploy is misconfigured" apart from "a real caller sent a bad token" —
    callers map this to 503, UnauthorizedError to 401. Neither ever admits
    the request.
    """


class MystiraPrincipal:
    """The authenticated principal, derived from a validated token's claims."""

    def __init__(self, subject: str, email: Optional[str], roles: List[str]):
        self.id = subject
        self.email = email
        self.roles = roles

    def __getitem__(self, key: str) -> Any:
        # Dict-style access (user["id"]) for call sites written against the
        # old mock {"id": ...} shape.
        return getattr(self, key)

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _get_config() -> Tuple[str, List[str]]:
    issuer = (os.environ.get("MYSTIRA_OIDC_ISSUER") or "").strip()
    audience_raw = (os.environ.get("MYSTIRA_OIDC_AUDIENCE") or "").strip()
    audiences = [a.strip() for a in audience_raw.split(",") if a.strip()]

    if not issuer or not audiences:
        raise AuthNotConfiguredError(
            "MYSTIRA_OIDC_ISSUER and MYSTIRA_OIDC_AUDIENCE must both be set to "
            "validate Mystira Identity tokens. xtox's celladore-xtox OIDC "
            "client is not yet seeded on the Mystira Identity IdP (ADR-0029 "
            "addendum-02 is still Draft, unreviewed) so this is expected to "
            "be unset in every real environment today."
        )
    return issuer, audiences


def _get_jwks_client(issuer: str) -> PyJWKClient:
    now = time.time()
    with _lock:
        cached = _discovery_cache.get(issuer)
        if cached and now - cached[0] < _DISCOVERY_CACHE_TTL_SECONDS:
            jwks_uri = cached[1]
        else:
            discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
            with urllib.request.urlopen(discovery_url, timeout=5) as resp:
                doc = json.loads(resp.read())
            jwks_uri = doc["jwks_uri"]
            _discovery_cache[issuer] = (now, jwks_uri)

        client = _jwks_clients.get(jwks_uri)
        if client is None:
            client = PyJWKClient(jwks_uri)
            _jwks_clients[jwks_uri] = client
        return client


def extract_bearer_token(authorization_header: Optional[str]) -> str:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise UnauthorizedError("No valid authentication token provided")
    token = authorization_header.split(" ", 1)[1].strip()
    if not token:
        raise UnauthorizedError("No valid authentication token provided")
    return token


def validate_bearer_token(token: str) -> MystiraPrincipal:
    """Validate a Mystira Identity access token and return its principal.

    Raises AuthNotConfiguredError if MYSTIRA_OIDC_ISSUER/AUDIENCE are unset,
    or UnauthorizedError for any invalid/expired/untrusted token. Never
    returns a partially-trusted principal.
    """
    issuer, audiences = _get_config()  # raises AuthNotConfiguredError if unset

    try:
        jwks_client = _get_jwks_client(issuer)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audiences,
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError as e:
        logger.warning("Rejected Mystira token: %s", e)
        raise UnauthorizedError("Invalid or expired authentication token") from e
    except AuthError:
        raise
    except Exception as e:  # discovery/network failures, malformed JWKS, etc.
        logger.error("Mystira token validation error: %s", e)
        raise UnauthorizedError("Authentication failed") from e

    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError("Token missing subject claim")

    # house-of-veritas's OIDC pattern (auth.ts:isEmailVerified) never trusts an
    # `email` claim unless `email_verified` is also true — an IdP-registered
    # but unverified address could otherwise be used to impersonate/auto-link
    # to an existing account by email elsewhere in the app. Mirrored here even
    # though nothing in xtox keys off `.email` today, so that guarantee holds
    # if something starts to. IdPs differ in whether they serialize the claim
    # as a bool or a string, so both are accepted.
    email_verified = payload.get("email_verified")
    email = payload.get("email") if email_verified in (True, "true") else None

    # NOTE: unlike hov, Mystira Identity does not appear to issue an
    # app-specific role/roles claim at all — hov's own roles are entirely
    # local (looked up by email against its Postgres user table, never read
    # off the token). Nothing in xtox currently calls .has_role()/.roles; this
    # stays populated only in case a real "roles" claim shows up later, and
    # must not be treated as validated against hov's pattern.
    roles = payload.get("roles") or payload.get("role") or []
    if isinstance(roles, str):
        roles = [roles]

    return MystiraPrincipal(subject=subject, email=email, roles=list(roles))
