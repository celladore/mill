"""
Streaming utilities for handling large file uploads and downloads.

TODO: Production enhancements:
- Add progress tracking for streaming uploads
- Implement chunked reading with configurable chunk size
- Add streaming validation (e.g., file type detection from stream)
- Support resumable uploads
- Add bandwidth throttling for downloads
"""

import logging
from pathlib import Path
from typing import AsyncIterator, Optional

import aiofiles

logger = logging.getLogger(__name__)

# Chunk size for streaming operations (64KB)
STREAM_CHUNK_SIZE = 64 * 1024


async def stream_file_to_disk(
    source: AsyncIterator[bytes],
    destination: Path,
    max_size: Optional[int] = None
) -> int:
    """
    Stream file content from async iterator to disk.
    
    Args:
        source: Async iterator yielding bytes chunks
        destination: Path to write file
        max_size: Maximum file size in bytes (None for unlimited)
    
    Returns:
        Total bytes written
    
    Raises:
        ValueError: If file exceeds max_size
    """
    total_bytes = 0
    
    # POC: Streaming file write. For production, add:
    # - Progress callbacks
    # - Checksum validation
    # - Atomic writes (write to temp, then rename)
    async with aiofiles.open(destination, 'wb') as f:
        async for chunk in source:
            if max_size and total_bytes + len(chunk) > max_size:
                # Clean up partial file
                try:
                    await aiofiles.os.remove(destination)
                except Exception:
                    pass
                raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
            
            await f.write(chunk)
            total_bytes += len(chunk)
    
    logger.info(f"Streamed {total_bytes} bytes to {destination}")
    return total_bytes


async def stream_file_from_disk(
    source: Path,
    chunk_size: int = STREAM_CHUNK_SIZE
) -> AsyncIterator[bytes]:
    """
    Stream file content from disk as async iterator.
    
    Args:
        source: Path to file to read
        chunk_size: Size of each chunk in bytes
    
    Yields:
        Bytes chunks
    """
    # POC: Streaming file read. For production, add:
    # - Progress tracking
    # - Error recovery
    # - Bandwidth throttling
    async with aiofiles.open(source, 'rb') as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            yield chunk


async def stream_upload_file(
    upload_file,
    destination: Path,
    max_size: Optional[int] = None
) -> int:
    """
    Stream FastAPI UploadFile to disk.
    
    Args:
        upload_file: FastAPI UploadFile object
        destination: Path to write file
        max_size: Maximum file size in bytes
    
    Returns:
        Total bytes written
    """
    # POC: Using FastAPI's built-in streaming. For production:
    # - Add progress tracking
    # - Implement resumable uploads
    # - Add virus scanning integration
    total_bytes = 0
    
    async with aiofiles.open(destination, 'wb') as f:
        while True:
            chunk = await upload_file.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            
            if max_size and total_bytes + len(chunk) > max_size:
                # Clean up partial file
                try:
                    await aiofiles.os.remove(destination)
                except Exception:
                    pass
                raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
            
            await f.write(chunk)
            total_bytes += len(chunk)
    
    # Reset file pointer for potential reuse
    await upload_file.seek(0)
    
    # Deliberately omit upload_file.filename: destination is a generated temp
    # path (not derived from the user-supplied filename), so logging it here
    # avoids writing the original filename to logs.
    logger.info(f"Streamed {total_bytes} bytes to {destination}")
    return total_bytes

