import re
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

# Request/Response Models


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
    target_format: str = 'mp3'
    bitrate: str = '192k'
    sample_rate: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    @field_validator('target_format')
    @classmethod
    def validate_target_format(cls, v):
        """Validate target audio format."""
        valid_formats = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'}
        if v.lower() not in valid_formats:
            formats_str = ', '.join(valid_formats)
            raise ValueError(
                f"Invalid target format. Must be one of: {formats_str}"
            )
        return v.lower()

    @field_validator('bitrate')
    @classmethod
    def validate_bitrate(cls, v):
        """Validate bitrate format."""
        # Expected format: number followed by 'k'
        if not re.match(r'^\d+k$', v.lower()):
            raise ValueError(
                "Bitrate must be in format 'XXXk' "
                "(e.g., '128k', '192k', '320k')"
            )
        # Extract numeric value
        bitrate_num = int(v.lower().rstrip('k'))
        # Validate range (32k to 512k)
        if bitrate_num < 32 or bitrate_num > 512:
            raise ValueError("Bitrate must be between 32k and 512k")
        return v.lower()

    @field_validator('sample_rate')
    @classmethod
    def validate_sample_rate(cls, v):
        """Validate sample rate if provided."""
        if v is not None:
            # Common sample rates
            valid_rates = {8000, 11025, 16000, 22050, 44100, 48000, 96000}
            if v not in valid_rates:
                rates_str = ', '.join(map(str, sorted(valid_rates)))
                raise ValueError(
                    f"Sample rate must be one of: {rates_str}"
                )
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
