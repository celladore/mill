import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services import video_service
from services.video_service import VideoService, probe_video


class Collection:
    def __init__(self):
        self.records = []

    async def insert_one(self, record):
        self.records.append(record)


def test_probe_video_extracts_stream_metadata(monkeypatch, tmp_path):
    payload = {
        "format": {"duration": "12.345"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30000/1001",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }

    async def run(*_args, **_kwargs):
        return json.dumps(payload).encode()

    monkeypatch.setattr(video_service, "_run_process", run)
    result = asyncio.run(probe_video(tmp_path / "clip.mp4"))
    assert result == {
        "duration": 12.345,
        "width": 1280,
        "height": 720,
        "frame_rate": 29.97,
        "video_codec": "h264",
        "audio_codec": "aac",
    }


def test_video_conversion_is_bounded_persisted_and_owner_scoped(monkeypatch, tmp_path):
    monkeypatch.setattr(video_service, "TEMP_DIR", tmp_path)
    source = tmp_path / "clip.mov"
    source.write_bytes(b"source-video")
    collection = Collection()
    monkeypatch.setattr(
        video_service.Database,
        "get_db",
        lambda: SimpleNamespace(video_conversions=collection),
    )

    commands = []

    async def run(*args, **_kwargs):
        commands.append(args)
        output = Path(args[-1])
        if args[0] == "ffmpeg":
            output.write_bytes(b"converted-video")
        return b""

    probes = iter(
        [
            {
                "duration": 12.4,
                "width": 1920,
                "height": 1080,
                "frame_rate": 30.0,
                "video_codec": "hevc",
                "audio_codec": "aac",
            },
            {
                "duration": 12.4,
                "width": 1280,
                "height": 720,
                "frame_rate": 30.0,
                "video_codec": "h264",
                "audio_codec": "aac",
            },
        ]
    )

    async def probe(_path):
        return next(probes)

    async def upload(path, **kwargs):
        assert path.read_bytes() == b"converted-video"
        assert kwargs["kind"] == "video"
        assert kwargs["user_id"] == "user-1"
        return SimpleNamespace(
            created=True,
            blob_name="video/conversion",
            as_record=lambda: {
                "artifact_blob_name": "video/conversion",
                "artifact_available": True,
            },
        )

    monkeypatch.setattr(video_service, "_run_process", run)
    monkeypatch.setattr(video_service, "probe_video", probe)
    monkeypatch.setattr(video_service.ArtifactStorageService, "upload", upload)
    result = asyncio.run(
        VideoService.process_video_file(
            source, "clip.mov", "mp4", "balanced", 720, "user-1"
        )
    )

    ffmpeg = next(command for command in commands if command[0] == "ffmpeg")
    assert "libx264" in ffmpeg
    assert "scale=w=-2:h='min(720,ih)'" in ffmpeg
    assert result.target_format == "mp4"
    assert result.width == 1280
    assert result.height == 720
    assert result.video_codec == "h264"
    assert collection.records[0]["user_id"] == "user-1"
    assert collection.records[0]["artifact_blob_name"] == "video/conversion"


def test_video_conversion_rejects_sources_above_8k(monkeypatch, tmp_path):
    monkeypatch.setattr(video_service, "TEMP_DIR", tmp_path)
    source = tmp_path / "oversized.mp4"
    source.write_bytes(b"video")

    async def probe(_path):
        return {
            "duration": 10.0,
            "width": 8000,
            "height": 5000,
            "frame_rate": 24.0,
            "video_codec": "h264",
            "audio_codec": None,
        }

    monkeypatch.setattr(video_service, "probe_video", probe)
    with pytest.raises(HTTPException, match="8K limit"):
        asyncio.run(
            VideoService.process_video_file(
                source, "oversized.mp4", "mp4", "balanced", 1080, "user-1"
            )
        )
