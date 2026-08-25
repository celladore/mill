"""
Security utilities for file handling and validation.
"""

import re
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal and other security issues.
    
    Args:
        filename: Original filename
        max_length: Maximum allowed filename length
        
    Returns:
        Sanitized filename safe for use in file operations
        
    TODO: Production hardening:
    - Add filename allowlist/blocklist patterns
    - Implement filename normalization (Unicode)
    - Add logging for rejected filenames
    - Consider using uuid-based filenames with extension preservation
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove path components to prevent directory traversal
    filename = os.path.basename(filename)
    
    # Remove any remaining path separators
    filename = filename.replace('/', '').replace('\\', '')
    
    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Remove leading/trailing dots and spaces (Windows issue)
    filename = filename.strip('. ')
    
    # Replace dangerous characters with underscore
    # Allow: alphanumeric, dash, underscore, dot
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_length = max_length - len(ext)
        filename = name[:max_name_length] + ext
    
    # Ensure filename is not empty after sanitization
    if not filename or filename in ('.', '..'):
        raise ValueError(f"Filename '{filename}' is invalid after sanitization")
    
    return filename


def validate_file_path(base_dir: Path, file_path: Path) -> Path:
    """
    Validate that a file path is within the base directory (prevent path traversal).
    
    Args:
        base_dir: Base directory that file must be within
        file_path: File path to validate
        
    Returns:
        Resolved, validated Path object
        
    Raises:
        ValueError: If path is outside base directory
        
    TODO: Production hardening:
    - Add symlink detection
    - Implement path canonicalization
    - Add audit logging for path validation failures
    """
    # Resolve both paths to absolute paths
    base_dir = base_dir.resolve()
    file_path = file_path.resolve()
    
    # Check if file_path is within base_dir
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        logger.error(
            f"Path traversal attempt detected: {file_path} is outside {base_dir}"
        )
        raise ValueError(f"Invalid file path: path traversal detected")
    
    return file_path


def validate_target_format(target_format: str, allowed_formats: set) -> str:
    """
    Validate a user-supplied target format against an explicit allowlist.

    Must run before target_format is used in ANY filesystem path
    construction (e.g. f"{conversion_id}.{target_format}"). Relying on a
    downstream converter to reject an unsupported format is not a
    substitute: the literal, unsanitized value is still used to build a
    path in the code between the request and that later check, which is
    exactly the path-injection shape static analysis (and a real attacker)
    will flag.

    Args:
        target_format: Raw format string from the request
        allowed_formats: Lowercase extensions this endpoint accepts

    Returns:
        The normalized (stripped, lowercased) format string

    Raises:
        ValueError: If target_format is not one of allowed_formats
    """
    normalized = target_format.strip().lower()
    if normalized not in allowed_formats:
        raise ValueError(
            f"Unsupported target format '{target_format}'. "
            f"Allowed: {', '.join(sorted(allowed_formats))}"
        )
    return normalized


def get_safe_temp_filename(original_filename: str, conversion_id: str) -> str:
    """
    Generate a safe temporary filename using conversion ID.
    
    Args:
        original_filename: Original filename (for extension extraction)
        conversion_id: Unique conversion ID
        
    Returns:
        Safe filename: {conversion_id}.{extension}
    """
    # Extract extension from original filename
    ext = Path(original_filename).suffix.lower()
    
    # Sanitize extension
    if ext:
        ext = sanitize_filename(ext, max_length=10)
        if not ext.startswith('.'):
            ext = '.' + ext
    
    return f"{conversion_id}{ext}"

