"""JWE unwrap for Mystira Identity access tokens (ADR-0029)."""

from __future__ import annotations

import base64
import os
import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwcrypto import jwe, jwk
from jwcrypto.common import base64url_encode

import mystira_auth
from mystira_auth import (
    AuthNotConfiguredError,
    UnauthorizedError,
    _is_jwe,
    _unwrap_access_token,
    validate_bearer_token,
)

ISSUER = "https://identity.mystira.app/"
AUDIENCE = "celladore-xtox"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _signed_jwt(private_key, *, extra_claims=None) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-1",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 900,
        "email": "user@example.com",
        "email_verified": True,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, private_key, algorithm="RS256")


def _encrypt_jwe(inner_jwt: str, key_bytes: bytes) -> str:
    key = jwk.JWK(kty="oct", k=base64url_encode(key_bytes))
    token = jwe.JWE(
        inner_jwt.encode("ascii"),
        protected={
            "alg": "A256KW",
            "enc": "A256CBC-HS512",
            "typ": "at+jwt",
            "cty": "JWT",
        },
        recipient=key,
    )
    return token.serialize(compact=True)


@pytest.fixture
def oidc_env(monkeypatch):
    key_bytes = os.urandom(32)
    monkeypatch.setenv("MYSTIRA_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("MYSTIRA_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("MYSTIRA_OIDC_ENCRYPTION_KEY", _b64(key_bytes))
    return key_bytes


def test_is_jwe_detects_five_segment_enc_header(oidc_env):
    private_key, _ = _rsa_keypair()
    compact = _encrypt_jwe(_signed_jwt(private_key), oidc_env)
    assert compact.count(".") == 4
    assert _is_jwe(compact)
    assert not _is_jwe(_signed_jwt(private_key))


def test_unwrap_decrypts_nested_jwt(oidc_env):
    private_key, _ = _rsa_keypair()
    inner = _signed_jwt(private_key)
    compact = _encrypt_jwe(inner, oidc_env)
    assert _unwrap_access_token(compact) == inner


def test_jwe_without_encryption_key_is_misconfigured(monkeypatch):
    monkeypatch.setenv("MYSTIRA_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("MYSTIRA_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("MYSTIRA_OIDC_ENCRYPTION_KEY", raising=False)
    private_key, _ = _rsa_keypair()
    compact = _encrypt_jwe(_signed_jwt(private_key), os.urandom(32))
    with pytest.raises(AuthNotConfiguredError, match="MYSTIRA_OIDC_ENCRYPTION_KEY"):
        _unwrap_access_token(compact)


def test_jwe_with_wrong_key_is_unauthorized(oidc_env):
    private_key, _ = _rsa_keypair()
    compact = _encrypt_jwe(_signed_jwt(private_key), os.urandom(32))
    with pytest.raises(UnauthorizedError):
        _unwrap_access_token(compact)


def test_plain_jws_does_not_require_encryption_key(monkeypatch):
    monkeypatch.delenv("MYSTIRA_OIDC_ENCRYPTION_KEY", raising=False)
    private_key, _ = _rsa_keypair()
    inner = _signed_jwt(private_key)
    assert _unwrap_access_token(inner) == inner


def test_validate_bearer_token_accepts_jwe(monkeypatch, oidc_env):
    private_key, public_key = _rsa_keypair()
    compact = _encrypt_jwe(_signed_jwt(private_key), oidc_env)

    fake_jwks = MagicMock()
    fake_jwks.get_signing_key_from_jwt.return_value.key = public_key
    monkeypatch.setattr(mystira_auth, "_get_jwks_client", lambda issuer: fake_jwks)

    principal = validate_bearer_token(compact)
    assert principal.id == "user-1"
    assert principal.email == "user@example.com"
    fake_jwks.get_signing_key_from_jwt.assert_called_once()
    inner = fake_jwks.get_signing_key_from_jwt.call_args[0][0]
    assert inner.count(".") == 2
    assert not _is_jwe(inner)
