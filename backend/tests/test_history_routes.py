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
                "artifact_available": True,
                "artifact_expires_at": now + timedelta(days=1),
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
        video_conversions=Collection(
            [
                {
                    "id": "video-own",
                    "user_id": "user-1",
                    "filename": "clip.mov",
                    "original_format": "mov",
                    "target_format": "mp4",
                    "success": True,
                    "artifact_available": True,
                    "artifact_expires_at": now + timedelta(days=1),
                    "input_file_size_kb": 4096.0,
                    "file_size_kb": 2048.0,
                    "duration": 12.4,
                    "width": 1280,
                    "height": 720,
                    "video_codec": "h264",
                    "quality": "balanced",
                    "timestamp": now - timedelta(seconds=15),
                }
            ]
        ),
        image_conversions=Collection(
            [
                {
                    "id": "image-own",
                    "user_id": "user-1",
                    "filename": "source.png",
                    "original_format": "png",
                    "target_format": "webp",
                    "success": True,
                    "artifact_available": True,
                    "artifact_expires_at": now + timedelta(days=1),
                    "input_file_size_kb": 512.0,
                    "file_size_kb": 128.5,
                    "width": 1200,
                    "height": 800,
                    "quality": "high",
                    "quality_value": 95,
                    "timestamp": now - timedelta(seconds=30),
                }
            ]
        ),
        transcriptions=transcriptions,
        text_conversions=Collection(
            [
                {
                    "id": "text-own",
                    "user_id": "user-1",
                    "filename": "notes",
                    "original_format": "md",
                    "target_format": "docx",
                    "success": True,
                    "artifact_available": True,
                    "artifact_expires_at": now + timedelta(days=1),
                    "timestamp": now - timedelta(minutes=1),
                },
                {
                    "id": "text-other",
                    "user_id": "user-2",
                    "filename": "other",
                    "original_format": "txt",
                    "target_format": "html",
                    "success": True,
                    "timestamp": now,
                },
            ]
        ),
        generated_texts=Collection(
            [
                {
                    "id": "generation-own",
                    "user_id": "user-1",
                    "filename": "generated-text",
                    "operation": "generate",
                    "target_format": "md",
                    "success": True,
                    "artifact_available": True,
                    "artifact_expires_at": now + timedelta(days=1),
                    "artifact_size_bytes": 2048,
                    "timestamp": now + timedelta(seconds=1),
                }
            ]
        ),
    )
    monkeypatch.setattr("routers.history.Database.get_db", lambda: database)

    result = asyncio.run(
        get_transformation_history(
            limit=50, offset=0, user=SimpleNamespace(id="user-1")
        )
    )

    assert [item.id for item in result] == [
        "generation-own",
        "transcript-own",
        "video-own",
        "image-own",
        "text-own",
        "doc-own",
    ]
    assert documents.last_query == {"user_id": "user-1"}
    assert result[0].kind == "generation"
    assert result[0].downloadable is True
    assert result[0].detail == "generate"
    assert result[0].output_size_kb == 2.0
    assert result[1].downloadable is False
    assert result[1].detail == "en"
    assert "private transcript text" not in str(result)
    video = result[2]
    assert video.kind == "video"
    assert video.detail == "12s · h264"
    assert video.input_size_kb == 4096.0
    assert video.output_size_kb == 2048.0
    image = result[3]
    assert image.detail == "1200 x 800"
    assert image.input_size_kb == 512.0
    assert image.output_size_kb == 128.5
    assert image.quality == "high"
    assert image.quality_value == 95
    assert result[4].kind == "text"
    assert result[4].downloadable is True
