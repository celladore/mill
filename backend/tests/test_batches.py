import asyncio
import copy
import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response, UploadFile

from capabilities import public_capabilities
from database import Database
from models import BatchCreateItem, BatchCreateRequest
from routers import batches


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, key, direction):
        self.documents.sort(
            key=lambda document: document.get(key), reverse=direction < 0
        )
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __aiter__(self):
        self.iterator = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return copy.deepcopy(next(self.iterator))
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query):
        return next(
            (copy.deepcopy(doc) for doc in self.documents if _matches(doc, query)), None
        )

    def find(self, query):
        return FakeCursor(
            [copy.deepcopy(doc) for doc in self.documents if _matches(doc, query)]
        )

    async def insert_one(self, document):
        self.documents.append(copy.deepcopy(document))

    async def insert_many(self, documents):
        self.documents.extend(copy.deepcopy(documents))

    async def delete_one(self, query):
        self.documents = [doc for doc in self.documents if not _matches(doc, query)]

    async def delete_many(self, query):
        self.documents = [doc for doc in self.documents if not _matches(doc, query)]

    async def update_one(self, query, update):
        document = await self.find_one_and_update(query, update)
        count = 1 if document else 0
        return SimpleNamespace(matched_count=count, modified_count=count)

    async def find_one_and_update(self, query, update, return_document=None):
        del return_document
        for document in self.documents:
            if not _matches(document, query):
                continue
            document.update(update.get("$set", {}))
            for key, value in update.get("$inc", {}).items():
                document[key] = document.get(key, 0) + value
            return copy.deepcopy(document)
        return None


class FakeDatabase:
    def __init__(self):
        self.batches = FakeCollection()
        self.batch_items = FakeCollection()


def _request(*names):
    digest = hashlib.sha256(b"test").hexdigest()
    return BatchCreateRequest(
        route="text",
        settings={"target_format": "html"},
        items=[BatchCreateItem(filename=name, size=4, sha256=digest) for name in names],
    )


def test_capabilities_keep_transcription_single_file():
    contract = public_capabilities()
    assert contract["routes"]["text"]["batch_enabled"] is True
    assert contract["routes"]["transcript"]["batch_enabled"] is False
    assert contract["batch"]["execution"] == "client_coordinated"


def test_idempotency_index_failure_stops_startup(monkeypatch):
    class RejectingCollection:
        async def create_index(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("index unavailable")

    monkeypatch.setattr(Database, "db", SimpleNamespace(batches=RejectingCollection()))
    with pytest.raises(RuntimeError, match="index unavailable"):
        asyncio.run(Database._create_indexes())


def test_create_is_idempotent_and_scoped_to_the_authenticated_user():
    async def run():
        db = FakeDatabase()
        owner = SimpleNamespace(id="owner")
        first = await batches.create_batch(
            _request("one.md", "two.md"), Response(), "retry-key", db, owner
        )
        second_response = Response()
        second = await batches.create_batch(
            _request("one.md", "two.md"), second_response, "retry-key", db, owner
        )

        assert first["id"] == second["id"]
        assert second_response.status_code == 200
        assert len(db.batches.documents) == 1
        assert len(db.batch_items.documents) == 2
        with pytest.raises(HTTPException) as changed:
            await batches.create_batch(
                _request("one.md", "changed.md"),
                Response(),
                "retry-key",
                db,
                owner,
            )
        assert changed.value.status_code == 409

        other = await batches.create_batch(
            _request("one.md", "two.md"),
            Response(),
            "retry-key",
            db,
            SimpleNamespace(id="other-user"),
        )
        assert other["id"] != first["id"]
        visible = await batches.get_batch(first["id"], db, owner)
        assert visible["id"] == first["id"]
        with pytest.raises(HTTPException) as hidden:
            await batches.get_batch(first["id"], db, SimpleNamespace(id="other-user"))
        assert hidden.value.status_code == 404

    asyncio.run(run())


def test_expired_claim_is_recovered_with_a_new_fencing_token(monkeypatch):
    async def run():
        db = FakeDatabase()
        owner = SimpleNamespace(id="owner")
        created = await batches.create_batch(
            _request("one.md", "two.md"), Response(), None, db, owner
        )
        item_id = created["items"][0]["id"]
        item = next(
            document
            for document in db.batch_items.documents
            if document["id"] == item_id
        )
        item.update(
            state="running",
            claim_token="abandoned-claim",  # noqa: S106 - lease token, not a credential
            attempts=1,
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )

        class Result:
            id = "result-recovered"

            @staticmethod
            def model_dump(mode=None):
                del mode
                return {
                    "id": "result-recovered",
                    "target_format": "html",
                    "success": True,
                }

        async def succeed(*args, **kwargs):
            return Result()

        monkeypatch.setattr(batches, "_execute", succeed)
        response = await batches.execute_batch_item(
            created["id"],
            item_id,
            UploadFile(filename="one.md", file=BytesIO(b"test")),
            db,
            owner,
        )
        assert response["item"]["state"] == "succeeded"
        stored = next(
            document
            for document in db.batch_items.documents
            if document["id"] == item_id
        )
        assert stored["attempts"] == 2
        assert stored["claim_token"] is None
        stale = await db.batch_items.update_one(
            {"id": item_id, "claim_token": "abandoned-claim"},
            {"$set": {"state": "failed"}},
        )
        assert stale.modified_count == 0

    asyncio.run(run())


def test_duplicate_filenames_are_rejected_before_records_are_written():
    async def run():
        db = FakeDatabase()
        with pytest.raises(HTTPException) as duplicate:
            await batches.create_batch(
                _request("same.md", "SAME.md"),
                Response(),
                None,
                db,
                SimpleNamespace(id="owner"),
            )
        assert duplicate.value.status_code == 400
        assert db.batches.documents == []
        assert db.batch_items.documents == []

    asyncio.run(run())


def test_batch_settings_enforce_single_file_bounds_and_normalize_quality():
    normalized = batches._validate_settings(
        "image", {"target_format": "webp", "quality": 85, "max_width": 16384}
    )
    assert normalized["quality"] == "85"
    with pytest.raises(HTTPException) as invalid_width:
        batches._validate_settings("image", {"max_width": 16385})
    assert invalid_width.value.status_code == 400
    with pytest.raises(HTTPException) as unknown:
        batches._validate_settings("image", {"unbounded": True})
    assert unknown.value.status_code == 400


def test_execution_rejects_same_name_and_size_with_different_content():
    async def run():
        with pytest.raises(HTTPException) as mismatch:
            await batches._execute(
                "text",
                UploadFile(filename="one.md", file=BytesIO(b"test")),
                {"target_format": "html"},
                "owner",
                4,
                hashlib.sha256(b"evil").hexdigest(),
            )
        assert mismatch.value.status_code == 400
        assert "content" in mismatch.value.detail

    asyncio.run(run())


def test_item_claims_are_terminal_and_partial_failure_is_preserved(monkeypatch):
    async def run():
        db = FakeDatabase()
        owner = SimpleNamespace(id="owner")
        created = await batches.create_batch(
            _request("one.md", "two.md"), Response(), None, db, owner
        )

        class Result:
            id = "result-1"

            @staticmethod
            def model_dump(mode=None):
                del mode
                return {"id": "result-1", "target_format": "html", "success": True}

        async def succeed(*args, **kwargs):
            return Result()

        monkeypatch.setattr(batches, "_execute", succeed)
        first = created["items"][0]
        response = await batches.execute_batch_item(
            created["id"],
            first["id"],
            UploadFile(filename="one.md", file=BytesIO(b"test")),
            db,
            owner,
        )
        assert response["item"]["state"] == "succeeded"

        async def fail(*args, **kwargs):
            raise HTTPException(status_code=400, detail="Invalid source")

        monkeypatch.setattr(batches, "_execute", fail)
        second = created["items"][1]
        response = await batches.execute_batch_item(
            created["id"],
            second["id"],
            UploadFile(filename="two.md", file=BytesIO(b"test")),
            db,
            owner,
        )
        assert response["batch"]["state"] == "partial_success"
        assert response["item"]["error_code"] == "http_400"

        repeated = await batches.execute_batch_item(
            created["id"],
            first["id"],
            UploadFile(filename="one.md", file=BytesIO(b"test")),
            db,
            owner,
        )
        assert repeated["state"] == "succeeded"

    asyncio.run(run())
