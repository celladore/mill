import asyncio

import pytest
from fastapi import HTTPException

from routers import status


class _Admin:
    def __init__(self, error=None):
        self.error = error

    async def command(self, command):
        assert command == "ping"
        if self.error:
            raise self.error
        return {"ok": 1}


class _Client:
    def __init__(self, error=None):
        self.admin = _Admin(error)


def test_health_is_explicitly_liveness_only():
    result = asyncio.run(status.health())
    assert result == {"status": "ok", "service": "mill-api", "check": "liveness"}


def test_ready_pings_database(monkeypatch):
    monkeypatch.setattr(status.Database, "client", _Client())
    result = asyncio.run(status.ready())
    assert result == {"status": "ready", "service": "mill-api", "check": "readiness"}


def test_ready_fails_closed_without_database(monkeypatch):
    monkeypatch.setattr(status.Database, "client", None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(status.ready())
    assert error.value.status_code == 503


def test_ready_fails_closed_when_ping_fails(monkeypatch):
    monkeypatch.setattr(status.Database, "client", _Client(RuntimeError("offline")))
    with pytest.raises(HTTPException) as error:
        asyncio.run(status.ready())
    assert error.value.status_code == 503
