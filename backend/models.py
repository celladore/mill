import re
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from capabilities import BATCH_MAX_ITEMS

# Request/Response Models


class BatchCreateItem(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BatchCreateRequest(BaseModel):
    route: Literal["document", "image", "text", "audio", "video"]
    settings: Dict[str, Any] = Field(default_factory=dict)
    items: List[BatchCreateItem] = Field(min_length=2, max_length=BATCH_MAX_ITEMS)


class ConversionRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    auto_fix: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversionResult(BaseModel):
    id: str
    filename: str
    success: bool
    auto_fix_applied: bool = False
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    pdf_path: Optional[str] = None
    fixed_content: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StatusCheckCreate(BaseModel):
    client_name: str


# Document storage models


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content_type: str
    size: int
    blob_name: str
    uploaded_by: Optional[str] = None
    permissions: Dict[str, List[str]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    uploaded_by: Optional[str] = None
    timestamp: datetime
    available_permissions: List[str]


class PermissionUpdate(BaseModel):
    user_id: str
    permissions: List[str]


# Audio conversion models


class AudioConversionRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    target_format: str = "mp3"
    bitrate: str = "192k"
    sample_rate: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target_format")
    @classmethod
    def validate_target_format(cls, v):
        """Validate target audio format."""
        valid_formats = {"mp3", "wav", "ogg", "m4a", "aac", "flac"}
        if v.lower() not in valid_formats:
            formats_str = ", ".join(valid_formats)
            raise ValueError(f"Invalid target format. Must be one of: {formats_str}")
        return v.lower()

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v):
        """Validate bitrate format."""
        # Expected format: number followed by 'k'
        if not re.match(r"^\d+k$", v.lower()):
            raise ValueError(
                "Bitrate must be in format 'XXXk' " "(e.g., '128k', '192k', '320k')"
            )
        # Extract numeric value
        bitrate_num = int(v.lower().rstrip("k"))
        # Validate range (32k to 512k)
        if bitrate_num < 32 or bitrate_num > 512:
            raise ValueError("Bitrate must be between 32k and 512k")
        return v.lower()

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v):
        """Validate sample rate if provided."""
        if v is not None:
            # Common sample rates
            valid_rates = {8000, 11025, 16000, 22050, 44100, 48000, 96000}
            if v not in valid_rates:
                rates_str = ", ".join(map(str, sorted(valid_rates)))
                raise ValueError(f"Sample rate must be one of: {rates_str}")
        return v


class AudioConversionResult(BaseModel):
    id: str
    filename: str
    original_format: str
    target_format: str
    success: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    audio_path: Optional[str] = None
    file_size_kb: Optional[float] = None
    duration: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VideoConversionResult(BaseModel):
    id: str
    filename: str
    original_format: str
    target_format: str
    success: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    input_file_size_kb: Optional[float] = None
    file_size_kb: Optional[float] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    quality: Optional[str] = None
    max_height: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Image conversion models


class ImageConversionRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    target_format: str = "jpeg"
    quality: str = "high"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target_format")
    @classmethod
    def validate_target_format(cls, v):
        """Validate target image format."""
        # Raster targets mirror ImageConverter; SVG uses SvgVectorizer.
        valid_formats = {"jpeg", "jpg", "png", "webp", "bmp", "tiff", "gif", "svg"}
        if v.lower() not in valid_formats:
            formats_str = ", ".join(sorted(valid_formats))
            raise ValueError(f"Invalid target format. Must be one of: {formats_str}")
        return v.lower()

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v):
        """Validate quality preset."""
        valid_presets = {"high", "medium", "low", "web"}
        if v.lower() not in valid_presets:
            presets_str = ", ".join(sorted(valid_presets))
            raise ValueError(f"Invalid quality preset. Must be one of: {presets_str}")
        return v.lower()


class ImageConversionResult(BaseModel):
    id: str
    filename: str
    original_format: str
    target_format: str
    success: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    image_path: Optional[str] = None
    input_file_size_kb: Optional[float] = None
    file_size_kb: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    quality: Optional[str] = None
    quality_value: Optional[int] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    metadata_stripped: bool = True
    vector_colors: Optional[int] = None
    vector_paths: Optional[int] = None
    vector_detail: Optional[int] = None
    path_smoothing: Optional[int] = None
    background_removed: Optional[bool] = None
    # Owning principal's subject (MystiraPrincipal.id). Optional so records
    # written before this field existed still deserialize; new records
    # always set it, and download/result routes filter on it -- see
    # ConversionBusinessLogic.get_image_conversion_result / get_image_file_path.
    user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Compatibility field retained in the response model. New artifact
    # availability uses internal artifact_expires_at metadata in Mongo.
    expires_at: Optional[datetime] = None


# Transcription models


class TranscriptionResult(BaseModel):
    id: str
    filename: str
    success: bool
    text: Optional[str] = None
    language: Optional[str] = None
    duration: Optional[float] = None
    source_conversion_id: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TextConversionResult(BaseModel):
    """Result metadata for a deterministic text-format conversion."""

    id: str
    filename: str
    original_format: str
    target_format: str
    success: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    file_size_kb: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GenerativeTextRequest(BaseModel):
    """Bounded input for the non-deterministic Generate / Rewrite lane."""

    operation: Literal["generate", "rewrite"]
    input: str = Field(min_length=1, max_length=50_000)
    instructions: Optional[str] = Field(default=None, max_length=4_000)
    output_format: Literal["txt", "md"] = "md"
    max_output_tokens: int = Field(default=1_200, ge=64, le=4_000)

    @field_validator("input")
    @classmethod
    def validate_input(cls, value):
        if not value.strip():
            raise ValueError("Input must contain visible text")
        return value


class GenerativeTextResult(BaseModel):
    id: str
    filename: str
    operation: Literal["generate", "rewrite"]
    target_format: Literal["txt", "md"]
    success: bool
    output_text: str
    model_alias: str
    usage: Dict[str, int] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TransformationHistoryItem(BaseModel):
    """A privacy-safe, normalized row for the workspace activity ledger."""

    id: str
    kind: str
    filename: str
    input_format: Optional[str] = None
    output_format: str
    success: bool
    timestamp: datetime
    downloadable: bool = False
    retained: bool = True
    artifact_expires_at: Optional[datetime] = None
    detail: Optional[str] = None
    input_size_kb: Optional[float] = None
    output_size_kb: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    quality: Optional[str] = None
    quality_value: Optional[int] = None
