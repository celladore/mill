"""
MCP (Model Context Protocol) stdio server exposing xtox's image conversion
as callable tools.

Runs entirely in-process against core/image_converter.py — it does not call
the deployed HTTP API. The API's routes all sit behind Mystira OIDC
(backend/auth.py get_current_user), so a thin HTTP-proxy server would need
to acquire and refresh a bearer token itself; that's a separate integration
this server intentionally does not take on. Running local-and-offline also
means it keeps working when the API is down or not yet deployed.

Usage (stdio transport — one client per process):
    python mcp_server/server.py

Register with Claude Code:
    claude mcp add xtox-images -- python /absolute/path/to/mcp_server/server.py

See mcp_server/README.md for the full registration snippet (including the
.mcp.json form) and the list of tools this server exposes.
"""
import base64
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Optional

# Load core/image_converter.py directly by path rather than `import core` or
# `from core import ImageConverter`. core/__init__.py eagerly imports every
# document converter (LaTeX, DOCX, HTML, ...) and their unrelated optional
# dependencies; this server only needs Pillow. Same pattern as
# backend/services/audio_service.py and backend/services/image_service.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_image_converter_path = _REPO_ROOT / "core" / "image_converter.py"
_spec = importlib.util.spec_from_file_location("xtox_image_converter", _image_converter_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load image converter from {_image_converter_path}")
_image_converter_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_image_converter_module)
ImageConverter = _image_converter_module.ImageConverter

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from mcp.types import ImageContent, TextContent  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("xtox-mcp")

mcp = MCPServer(
    name="xtox-images",
    version="1.0.0",
    instructions=(
        "Convert and inspect image files (JPEG, PNG, WebP, BMP, TIFF, GIF) "
        "using xtox's Pillow-backed converter. Prefer convert_image when "
        "both the client and server share a filesystem (e.g. Claude Code); "
        "use convert_image_base64 when the client can only send/receive "
        "inline image bytes (e.g. a chat client with no shared disk)."
    ),
)

_converter = ImageConverter()

# Kept in sync with core.image_converter.ImageConverter.SUPPORTED_FORMATS
# and backend/utils/file_validator.py's FileValidator.IMAGE_EXTENSIONS.
_MIME_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "gif": "image/gif",
}


def _require_supported_format(target_format: str) -> str:
    fmt = target_format.lower()
    if fmt not in ImageConverter.SUPPORTED_FORMATS:
        supported = ", ".join(sorted(ImageConverter.SUPPORTED_FORMATS))
        # ToolError (not ValueError): this is an anticipated bad-input failure,
        # so the client sees this exact message instead of a generic
        # "Error executing tool ..." with the reason withheld. See
        # mcp.server.mcpserver.exceptions.ToolError's docstring.
        raise ToolError(f"Unsupported target_format '{target_format}'. Supported: {supported}")
    return fmt


def _require_quality_preset(quality: str) -> str:
    q = quality.lower()
    if q not in _converter.quality_presets:
        presets = ", ".join(sorted(_converter.quality_presets))
        raise ToolError(f"Unknown quality preset '{quality}'. Supported: {presets}")
    return q


@mcp.tool()
def list_supported_formats() -> dict:
    """List the image formats this server can read and convert to."""
    return {
        "formats": sorted(ImageConverter.SUPPORTED_FORMATS.keys()),
        "quality_presets": sorted(_converter.quality_presets.keys()),
    }


@mcp.tool()
def get_image_info(path: str) -> dict:
    """
    Inspect an image file on disk.

    Args:
        path: Absolute or relative path to an image file readable by the server.

    Returns format, color mode, dimensions, file size in KB, and whether the
    image has transparency.
    """
    input_path = Path(path)
    if not input_path.is_file():
        raise ToolError(f"No such file: {input_path}")
    try:
        return _converter.get_image_info(input_path)
    except Exception as e:
        raise ToolError(f"Could not read '{input_path}' as an image: {e}") from e


@mcp.tool()
def convert_image(
    input_path: str,
    target_format: str,
    output_path: Optional[str] = None,
    quality: str = "high",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
) -> dict:
    """
    Convert an image file on disk to another format (e.g. JPEG -> WebP).

    Args:
        input_path: Path to the source image (jpeg, png, webp, bmp, tiff, or gif).
        target_format: Format to convert to (jpeg, png, webp, bmp, tiff, gif).
        output_path: Where to write the result. Defaults to input_path with
            its extension swapped to target_format, alongside the source file.
        quality: Quality preset — 'high' (95), 'medium' (75), 'low' (50), or
            'web' (85). Only affects lossy formats (JPEG, WebP).
        max_width: Optional max width in pixels; the image is downscaled to
            fit while preserving aspect ratio (requires max_height too).
        max_height: Optional max height in pixels (requires max_width too).

    Returns the output path, resulting dimensions, and file size in KB.
    """
    fmt = _require_supported_format(target_format)
    q = _require_quality_preset(quality)

    src = Path(input_path)
    if not src.is_file():
        raise ToolError(f"No such file: {src}")

    max_size = None
    if max_width is not None or max_height is not None:
        if max_width is None or max_height is None:
            raise ToolError("max_width and max_height must be provided together")
        max_size = (max_width, max_height)

    dest = Path(output_path) if output_path else None
    try:
        result_path = _converter.convert_image(
            src,
            output_path=dest,
            target_format=fmt,
            quality=q,
            max_size=max_size,
        )
        info = _converter.get_image_info(result_path)
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to convert '{src}' to {fmt}: {e}") from e
    logger.info("Converted %s -> %s (%s)", src, result_path, fmt)
    return {
        "output_path": str(result_path),
        "original_format": src.suffix.lstrip(".").lower(),
        "target_format": fmt,
        "width": info["width"],
        "height": info["height"],
        "file_size_kb": round(info["file_size_kb"], 2),
    }


@mcp.tool()
def convert_image_base64(
    image_base64: str,
    filename: str,
    target_format: str,
    quality: str = "high",
) -> list:
    """
    Convert base64-encoded image bytes to another format and return the
    result inline, for clients with no filesystem shared with this server.

    Args:
        image_base64: The source image, base64-encoded (no data: URI prefix).
        filename: Original filename (its extension identifies the source
            format, e.g. 'photo.jpg').
        target_format: Format to convert to (jpeg, png, webp, bmp, tiff, gif).
        quality: Quality preset — 'high', 'medium', 'low', or 'web'.

    Returns an image content block with the converted bytes plus a text
    summary (dimensions, resulting size in KB).
    """
    import tempfile

    fmt = _require_supported_format(target_format)
    q = _require_quality_preset(quality)

    suffix = Path(filename).suffix or ".bin"
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception as e:
        raise ToolError(f"image_base64 is not valid base64: {e}") from e

    try:
        with tempfile.TemporaryDirectory(prefix="xtox-mcp-") as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / f"input{suffix}"
            src.write_bytes(raw)

            dest = tmp_dir / f"output.{fmt}"
            result_path = _converter.convert_image(
                src, output_path=dest, target_format=fmt, quality=q
            )
            info = _converter.get_image_info(result_path)
            out_bytes = Path(result_path).read_bytes()
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to convert '{filename}' to {fmt}: {e}") from e

    mime_type = _MIME_TYPES[fmt]
    summary = (
        f"Converted {filename} to {fmt} "
        f"({info['width']}x{info['height']}, {info['file_size_kb']:.1f} KB)"
    )
    return [
        TextContent(type="text", text=summary),
        ImageContent(type="image", data=base64.b64encode(out_bytes).decode("ascii"), mime_type=mime_type),
    ]


if __name__ == "__main__":
    mcp.run()
