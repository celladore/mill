import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

from database import Database
from models import PermissionUpdate
from routers.documents import update_permissions, upload_document
from services.document_storage_service import DocumentStorageService
from starlette.datastructures import UploadFile


def test_upload_persists_blob_metadata(monkeypatch):
    documents = SimpleNamespace(insert_one=AsyncMock())
    monkeypatch.setattr(
        Database, "get_db", lambda: SimpleNamespace(documents=documents)
    )
    upload = AsyncMock(return_value=("user-1/blob/report.txt", 5, "text/plain"))
    monkeypatch.setattr(DocumentStorageService, "upload", upload)

    result = asyncio.run(
        upload_document(
            UploadFile(filename="report.txt", file=BytesIO(b"hello")),
            user=SimpleNamespace(id="user-1"),
        )
    )

    assert result.filename == "report.txt"
    assert result.size == 5
    assert result.available_permissions == ["read", "write", "share"]
    documents.insert_one.assert_awaited_once()
    assert (
        documents.insert_one.await_args.args[0]["blob_name"] == "user-1/blob/report.txt"
    )


def test_owner_can_grant_document_read_access(monkeypatch):
    document = {
        "id": "document-1",
        "filename": "report.txt",
        "content_type": "text/plain",
        "size": 5,
        "blob_name": "user-1/blob/report.txt",
        "uploaded_by": "user-1",
        "permissions": {},
        "timestamp": "2026-08-21T00:00:00Z",
    }
    documents = SimpleNamespace(
        find_one=AsyncMock(return_value=document),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(
        Database, "get_db", lambda: SimpleNamespace(documents=documents)
    )

    result = asyncio.run(
        update_permissions(
            "document-1",
            PermissionUpdate(user_id="user-2", permissions=["read"]),
            user=SimpleNamespace(id="user-1"),
        )
    )

    documents.update_one.assert_awaited_once_with(
        {"id": "document-1"},
        {"$set": {"permissions.user-2": ["read"]}},
    )
    assert result.available_permissions == ["read", "write", "share"]
