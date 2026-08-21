import asyncio
import inspect

import pytest
from fastapi import HTTPException

import auth
from mystira_auth import ForbiddenError, UnauthorizedError, _enforce_delegated_scope
from routers.conversion import transcribe_audio

DIRECT_AUDIENCES = ["celladore-xtox"]
DELEGATED_AUDIENCES = ["neuralliquid-convolens-web"]


def test_direct_xtox_audience_does_not_require_delegated_scope():
    _enforce_delegated_scope(
        {"aud": "celladore-xtox"},
        DIRECT_AUDIENCES,
        DELEGATED_AUDIENCES,
        "xtox.transcribe",
    )


@pytest.mark.parametrize("scope_claim", ["xtox.transcribe", "openid xtox.transcribe"])
def test_delegated_audience_requires_and_accepts_transcription_scope(scope_claim):
    _enforce_delegated_scope(
        {"aud": "neuralliquid-convolens-web", "scope": scope_claim},
        DIRECT_AUDIENCES,
        DELEGATED_AUDIENCES,
        "xtox.transcribe",
    )


def test_delegated_audience_without_scope_is_forbidden():
    with pytest.raises(ForbiddenError):
        _enforce_delegated_scope(
            {"aud": "neuralliquid-convolens-web", "scope": "openid profile"},
            DIRECT_AUDIENCES,
            DELEGATED_AUDIENCES,
            "xtox.transcribe",
        )


def test_unconfigured_audience_is_unauthorized_even_with_scope():
    with pytest.raises(UnauthorizedError):
        _enforce_delegated_scope(
            {"aud": "unknown-client", "scope": "xtox.transcribe"},
            DIRECT_AUDIENCES,
            DELEGATED_AUDIENCES,
            "xtox.transcribe",
        )


def test_transcription_dependency_passes_only_configured_delegation(monkeypatch):
    captured = {}

    def validate(token, **kwargs):
        captured.update(token=token, **kwargs)
        return object()

    monkeypatch.setenv("MYSTIRA_OIDC_DELEGATED_AUDIENCES", "neuralliquid-convolens-web")
    monkeypatch.setenv("MYSTIRA_OIDC_TRANSCRIPTION_SCOPE", "xtox.transcribe")
    monkeypatch.setattr(auth, "validate_bearer_token", validate)

    asyncio.run(auth.get_transcription_user("Bearer signed-token"))

    assert captured == {
        "token": "signed-token",
        "delegated_audiences": ["neuralliquid-convolens-web"],
        "required_scope": "xtox.transcribe",
    }


def test_missing_delegated_scope_maps_to_forbidden(monkeypatch):
    def reject(*args, **kwargs):
        raise ForbiddenError("scope required")

    monkeypatch.setattr(auth, "validate_bearer_token", reject)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.get_transcription_user("Bearer signed-token"))

    assert exc.value.status_code == 403


def test_only_transcription_route_uses_delegated_auth_dependency():
    dependency = inspect.signature(transcribe_audio).parameters["user"].default
    assert dependency.dependency is auth.get_transcription_user
