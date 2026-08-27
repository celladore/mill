import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from routers.history import get_transformation_history


class Cursor:
    def __init__(self, items):
        self.items = items

    def sort(self, *_args):
        self.items.sort(key=lambda item: item["timestamp"], reverse=True)
        return self

    def limit(self, length):
        self.items = self.items[:length]
        return self

    async def to_list(self, length):
        return self.items[:length]


class Collection:
    def __init__(self, items):
        self.items = items
        self.last_query = None

    def find(self, query):
        self.last_query = query
        return Cursor(
            [item for item in self.items if item.get("user_id") == query["user_id"]]
        )


def test_unified_history_is_owner_scoped_sorted_and_privacy_safe(monkeypatch):
    now = datetime.now(UTC)
    documents = Collection(
        [
            {
                "id": "doc-own",
                "user_id": "user-1",
                "filename": "paper.tex",
                "success": True,
                "pdf_path": "/private/paper.pdf",
                "timestamp": now - timedelta(minutes=2),
            },
            {
                "id": "doc-other",
                "user_id": "user-2",
                "filename": "other.tex",
                "success": True,
                "timestamp": now,
            },
        ]
    )
    transcriptions = Collection(
        [
            {
                "id": "transcript-own",
                "user_id": "user-1",
                "filename": "meeting.ogg",
                "success": True,
                "text": "private transcript text",
                "language": "en",
                "timestamp": now,
            },
        ]
    )
    database = SimpleNamespace(
        conversions=documents,
        audio_conversions=Collection([]),
        image_conversions=Collection([]),
        transcriptions=transcriptions,
    )
    monkeypatch.setattr("routers.history.Database.get_db", lambda: database)

    result = asyncio.run(
        get_transformation_history(
            limit=50, offset=0, user=SimpleNamespace(id="user-1")
        )
    )

    assert [item.id for item in result] == ["transcript-own", "doc-own"]
    assert documents.last_query == {"user_id": "user-1"}
    assert result[0].downloadable is False
    assert result[0].detail == "en"
    assert "private transcript text" not in str(result)
