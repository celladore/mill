"""
File validation utilities.

TODO: Production enhancements:
- Add MIME type validation (not just extension)
- Implement virus scanning integration
- Add file content validation (magic bytes)
- Support for custom validation rules
- Add validation result caching
"""

from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FileValidator:
    """Centralized file validation logic."""
    
    # Allowed file extensions
    LATEX_EXTENSIONS = {'.tex'}
    AUDIO_EXTENSIONS = {'.ogg', '.opus', '.mp3', '.wav', '.m4a', '.aac', '.flac'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp'}
    VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}
    
    @staticmethod
    def validate_latex_file(filename: str, file_size: int, max_size: int) -> Tuple[bool, Optional[str]]:
        """
        Validate LaTeX file.
        
        Returns:
            (is_valid, error_message)
        """
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in FileValidator.LATEX_EXTENSIONS:
            return False, f"Invalid file type. Only .tex files are supported."
        
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds {max_size_mb:.0f}MB limit."
        
        return True, None
    
    @staticmethod
    def validate_audio_file(filename: str, file_size: int, max_size: int) -> Tuple[bool, Optional[str]]:
        """
        Validate audio file.
        
        Returns:
            (is_valid, error_message)
        """
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in FileValidator.AUDIO_EXTENSIONS:
            allowed = ', '.join(FileValidator.AUDIO_EXTENSIONS)
            return False, f"Invalid audio format. Supported formats: {allowed}"
        
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds {max_size_mb:.0f}MB limit."
        
        return True, None
    
    @staticmethod
    def validate_image_file(filename: str, file_size: int, max_size: int) -> Tuple[bool, Optional[str]]:
        """
        Validate image file.
        
        Returns:
            (is_valid, error_message)
        """
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in FileValidator.IMAGE_EXTENSIONS:
            allowed = ', '.join(FileValidator.IMAGE_EXTENSIONS)
            return False, f"Invalid image format. Supported formats: {allowed}"
        
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds {max_size_mb:.0f}MB limit."
        
        return True, None
    @staticmethod
    def validate_video_file(
        filename: str, file_size: int, max_size: int
    ) -> Tuple[bool, Optional[str]]:
        """Validate a deterministic video-transcoding source."""
        file_ext = Path(filename).suffix.lower()
        if file_ext not in FileValidator.VIDEO_EXTENSIONS:
            allowed = ', '.join(sorted(FileValidator.VIDEO_EXTENSIONS))
            return False, f"Invalid video format. Supported formats: {allowed}"
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds {max_size_mb:.0f}MB limit."
        return True, None
