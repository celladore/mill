"""
Mystira Identity OIDC resource-server token validation.

xtox's API validates Bearer access tokens already issued by Mystira Identity's
OpenIddict authorization server. It does NOT perform the interactive
authorization_code+PKCE login handshake itself; the XtOX frontend does that as
the `celladore-xtox` Public + PKCE client. No client secret is held by the
browser or API, unlike house-of-veritas's confidential-RP setup.

ADR-0029 requires resource servers to validate offline: decrypt + signature +
exp. Mystira access tokens are JWE (`alg=A256KW`, `enc=A256CBC-HS512`) wrapping
a nested RS256 JWT. Decryption uses the shared OpenIddict symmetric key
(`MYSTIRA_OIDC_ENCRYPTION_KEY`) — a duplicate of Identity's `oidc-encryption-key`
KV secret, not a client secret and not a reason to make celladore-xtox
confidential.

STATUS (2026-08-21): ADR-0029 Addendum 02 is Accepted. Identity source confirms
interactive access tokens set `aud` to the requesting client id, so xtox's
audience is `celladore-xtox` and the issuer is
`https://identity.mystira.app/`. The client row was seeded in production by
Mystira workflow 32461392530. Missing config still fails CLOSED (503 via
AuthNotConfiguredError) — it never falls back to a bypass.

This module is intentionally duplicated in
azure-functions/shared_code/mystira_auth.py: the two runtimes deploy
independently (the Function App zip only ever contains azure-functions/) and
no shared pip-installable package exists across them yet. Keep both copies
in sync by hand; do not let them drift.
"""

from __future__ import annotations

import base64
import binascii
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
from jwcrypto import jwe, jwk
from jwcrypto.common import base64url_encode
from jwcrypto.jwe import InvalidJWEData

logger = logging.getLogger(__name__)

_DISCOVERY_CACHE_TTL_SECONDS = 3600
_lock = threading.Lock()
_discovery_cache: Dict[str, Tuple[float, str]] = {}  # issuer -> (fetched_at, jwks_uri)
_jwks_clients: Dict[str, PyJWKClient] = {}  # jwks_uri -> client

# OpenIddict's default access-token encryption, confirmed on live
# celladore-xtox tokens: {"alg":"A256KW","enc":"A256CBC-HS512","typ":"at+jwt","cty":"JWT"}.
_JWE_KEY_WRAP_ALG = "A256KW"
_JWE_CONTENT_ENC = "A256CBC-HS512"
_REQUIRED_ENCRYPTION_KEY_BYTES = 32


class AuthError(Exception):
    """Base class for authentication errors."""


class UnauthorizedError(AuthError):
    """A request had no valid Mystira-issued access token."""


class ForbiddenError(AuthError):
    """A valid Mystira token lacks the authorization required for this action."""


class AuthNotConfiguredError(AuthError):
    """MYSTIRA_OIDC_ISSUER / AUDIENCE / ENCRYPTION_KEY aren't set.

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
            "validate Mystira Identity tokens."
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


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded)


def _parse_jose_header(token: str) -> Dict[str, Any]:
    header_segment = token.split(".", 1)[0]
    return json.loads(_b64url_decode(header_segment))


def _is_jwe(token: str) -> bool:
    """True when the compact serialization is a JWE (5 segments + `enc` header)."""
    if token.count(".") != 4:
        return False
    try:
        header = _parse_jose_header(token)
    except (ValueError, json.JSONDecodeError, IndexError, binascii.Error):
        return False
    return bool(header.get("enc"))


def _encryption_key_from_env() -> bytes:
    material = (os.environ.get("MYSTIRA_OIDC_ENCRYPTION_KEY") or "").strip()
    if not material:
        raise AuthNotConfiguredError(
            "MYSTIRA_OIDC_ENCRYPTION_KEY must be set to decrypt Mystira Identity "
            "JWE access tokens (ADR-0029: resource servers validate offline via "
            "decrypt + signature + exp)."
        )
    try:
        key_bytes = base64.b64decode(material, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AuthNotConfiguredError(
            "MYSTIRA_OIDC_ENCRYPTION_KEY is set but is not valid base64. "
            "Expected Identity's 32-byte oidc-encryption-key secret."
        ) from exc
    if len(key_bytes) != _REQUIRED_ENCRYPTION_KEY_BYTES:
        raise AuthNotConfiguredError(
            "MYSTIRA_OIDC_ENCRYPTION_KEY must decode to exactly "
            f"{_REQUIRED_ENCRYPTION_KEY_BYTES} bytes (got {len(key_bytes)})."
        )
    return key_bytes


def _decrypt_jwe_to_nested_jwt(token: str, key_bytes: bytes) -> str:
    try:
        header = _parse_jose_header(token)
    except (ValueError, json.JSONDecodeError, IndexError, binascii.Error) as exc:
        raise UnauthorizedError("Invalid or expired authentication token") from exc

    if header.get("alg") != _JWE_KEY_WRAP_ALG or header.get("enc") != _JWE_CONTENT_ENC:
        logger.warning(
            "Rejected Mystira JWE with unexpected alg/enc: %s/%s",
            header.get("alg"),
            header.get("enc"),
        )
        raise UnauthorizedError("Invalid or expired authentication token")

    key = jwk.JWK(kty="oct", k=base64url_encode(key_bytes))
    jwetoken = jwe.JWE()
    try:
        jwetoken.deserialize(token)
        jwetoken.decrypt(key)
    except (InvalidJWEData, ValueError) as exc:
        logger.warning("Rejected Mystira JWE: %s", exc)
        raise UnauthorizedError("Invalid or expired authentication token") from exc

    payload = jwetoken.payload
    if not payload:
        raise UnauthorizedError("Invalid or expired authentication token")
    if isinstance(payload, bytes):
        return payload.decode("ascii")
    return str(payload)


def _unwrap_access_token(token: str) -> str:
    """Return the inner JWS, decrypting an OpenIddict JWE access token first."""
    if _is_jwe(token):
        return _decrypt_jwe_to_nested_jwt(token, _encryption_key_from_env())
    return token


def _claim_values(payload: Dict[str, Any], claim: str) -> List[str]:
    value = payload.get(claim)
    if isinstance(value, str):
        return [part for part in value.split() if part]
    if isinstance(value, list):
        return [str(part) for part in value if part]
    return []


def _enforce_delegated_scope(
    payload: Dict[str, Any],
    direct_audiences: List[str],
    delegated_audiences: List[str],
    required_scope: Optional[str],
) -> None:
    """Require an API-specific scope when a token targets another client.

    A direct XtOX-only token keeps the normal first-party path. Any token that
    includes a configured delegated client audience is accepted solely when it
    carries the dedicated scope, including mixed-audience tokens. This prevents
    adding a ConvoLens audience from silently granting access to XtOX.
    """
    token_audiences = set(_claim_values(payload, "aud"))
    delegated_match = token_audiences.intersection(delegated_audiences)
    if delegated_match:
        token_scopes = set(
            _claim_values(payload, "scope") + _claim_values(payload, "scp")
        )
        if not required_scope or required_scope not in token_scopes:
            raise ForbiddenError("Token lacks the required XtOX transcription scope")
        return

    if not token_audiences.intersection(direct_audiences):
        raise UnauthorizedError("Token audience is not authorized for XtOX")


def validate_bearer_token(
    token: str,
    *,
    delegated_audiences: Optional[List[str]] = None,
    required_scope: Optional[str] = None,
) -> MystiraPrincipal:
    """Validate a Mystira Identity access token and return its principal.

    Raises AuthNotConfiguredError if MYSTIRA_OIDC_ISSUER/AUDIENCE are unset,
    or if a JWE arrives without MYSTIRA_OIDC_ENCRYPTION_KEY. Raises
    UnauthorizedError for any invalid/expired/untrusted token. Never returns
    a partially-trusted principal.
    """
    issuer, direct_audiences = _get_config()  # raises AuthNotConfiguredError if unset
    delegated_audiences = delegated_audiences or []
    accepted_audiences = list(dict.fromkeys(direct_audiences + delegated_audiences))

    try:
        inner_token = _unwrap_access_token(token)
        jwks_client = _get_jwks_client(issuer)
        signing_key = jwks_client.get_signing_key_from_jwt(inner_token)
        payload = jwt.decode(
            inner_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=accepted_audiences,
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

    _enforce_delegated_scope(
        payload,
        direct_audiences,
        delegated_audiences,
        required_scope,
    )

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
