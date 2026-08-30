"""Authoritative conversion-route capabilities shared by API consumers."""

from config import (
    MAX_AUDIO_FILE_SIZE,
    MAX_FILE_SIZE,
    MAX_IMAGE_FILE_SIZE,
    MAX_VIDEO_FILE_SIZE,
)

BATCH_MAX_ITEMS = 10
BATCH_MAX_AGGREGATE_SIZE = 200 * 1024 * 1024
BATCH_RETENTION_SECONDS = 7 * 24 * 60 * 60
BATCH_ITEM_LEASE_SECONDS = 15 * 60
BATCH_MAX_ATTEMPTS = 2

ROUTE_CAPABILITIES = {
    "document": {
        "extensions": [".tex"],
        "targets": ["pdf"],
        "max_file_size": MAX_FILE_SIZE,
        "batch_enabled": True,
        "retention": "retained",
    },
    "image": {
        "extensions": [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"],
        "targets": ["webp", "jpeg", "png", "gif", "tiff", "bmp", "svg"],
        "max_file_size": MAX_IMAGE_FILE_SIZE,
        "batch_enabled": True,
        "retention": "retained",
    },
    "text": {
        "extensions": [".md", ".markdown", ".html", ".htm", ".txt", ".docx"],
        "targets": ["md", "html", "txt", "docx"],
        "max_file_size": MAX_FILE_SIZE,
        "batch_enabled": True,
        "retention": "retained",
    },
    "audio": {
        "extensions": [".ogg", ".opus", ".mp3", ".wav", ".m4a", ".aac", ".flac"],
        "targets": ["mp3", "wav", "ogg", "m4a", "aac", "flac"],
        "max_file_size": MAX_AUDIO_FILE_SIZE,
        "batch_enabled": True,
        "retention": "retained",
    },
    "transcript": {
        "extensions": [".ogg", ".opus", ".mp3", ".wav", ".m4a", ".aac", ".flac"],
        "targets": ["text"],
        "max_file_size": MAX_AUDIO_FILE_SIZE,
        "batch_enabled": False,
        "retention": "session_only",
    },
    "video": {
        "extensions": [".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"],
        "targets": ["mp4", "webm", "mov"],
        "max_file_size": MAX_VIDEO_FILE_SIZE,
        "batch_enabled": True,
        "retention": "retained",
    },
}


def public_capabilities() -> dict:
    return {
        "routes": ROUTE_CAPABILITIES,
        "batch": {
            "max_items": BATCH_MAX_ITEMS,
            "max_aggregate_size": BATCH_MAX_AGGREGATE_SIZE,
            "metadata_retention_seconds": BATCH_RETENTION_SECONDS,
            "item_lease_seconds": BATCH_ITEM_LEASE_SECONDS,
            "max_attempts": BATCH_MAX_ATTEMPTS,
            "execution": "client_coordinated",
        },
    }
