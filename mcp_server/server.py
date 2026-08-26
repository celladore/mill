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
import os
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

# Cap on the *decoded* size of an inline base64 payload passed to
# convert_image_base64. Without this, a caller can hand the server an
# arbitrarily large image_base64 string and force a same-sized allocation
# inside base64.b64decode() before any validation runs -- memory exhaustion
# on a stdio server with no other request-size limiting. Not shared with
# backend/config.py's MAX_IMAGE_FILE_SIZE: this server is intentionally
# standalone (see module docstring) and shouldn't import backend config,
# but 20 MiB matches that default so behavior is consistent either way.
_MAX_IMAGE_BASE64_BYTES = int(
    os.environ.get("XTOX_MCP_MAX_IMAGE_BYTES", 20 * 1024 * 1024)
)


def _require_supported_format(target_format: str) -> str:
    fmt = target_format.lower()
    if fmt not in ImageConverter.SUPPORTED_FORMATS:
        supported = ", ".join(sorted(ImageConverter.SUPPORTED_FORMATS))
        # ToolError (not ValueError): this is an anticipated bad-input failure,
        # so the client sees this exact message instead of a generic
        # "Error executing tool ..." with the reason withheld. See
        # mcp.server.mcpserver.exceptions.ToolError's docstring.
        raise ToolError(f"Unsupported target_format '{target_format}'. Supported: {supported}")
    # 'jpg' and 'jpeg' both map to Pillow's 'JPEG' in SUPPORTED_FORMATS, but
    # ImageConverter.convert_image() itself branches on
    # target_format.upper() == 'JPEG' -- once for the RGBA/P -> RGB flatten
    # before save (JPEG has no alpha channel), again to decide whether to
    # apply the quality setting. 'jpg'.upper() is 'JPG', which matches
    # neither, so an unnormalized 'jpg' silently skips both and can fail
    # outright on an RGBA/P source. Normalize once here so every caller of
    # this resolver (convert_image, convert_image_base64) gets a working
    # 'jpg'; every other format passes through unchanged.
    if fmt == "jpg":
        fmt = "jpeg"
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
            its extension swapped to target_format, alongside the source
            file -- or, if that would collide with input_path itself (e.g.
            converting a .jpeg to jpeg), input_path with a "-converted"
            suffix. Must not itself equal input_path.
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

    if output_path:
        dest = Path(output_path)
        # An explicit output_path that resolves to the same file as the
        # source would have ImageConverter open src for read and then,
        # while that handle may still be in use (Pillow loads pixel data
        # lazily), save over the same path -- undefined/corrupting.
        if dest.resolve() == src.resolve():
            raise ToolError(
                f"output_path must not be the same file as input_path ({src})"
            )
    else:
        # ImageConverter.convert_image() defaults an omitted output_path to
        # input_path.with_suffix(f'.{target_format}'), which collides with
        # the source whenever target_format matches the source's own
        # extension (e.g. photo.jpeg -> photo.jpeg, or photo.JPEG with the
        # jpg alias now normalized to jpeg above). Compute a default here
        # instead so a same-format request gets a distinct filename rather
        # than silently overwriting its own input.
        default_dest = src.with_suffix(f".{fmt}")
        if default_dest.name.lower() == src.name.lower():
            default_dest = src.with_name(f"{src.stem}-converted.{fmt}")
        dest = default_dest

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

    # Reject oversized payloads by their *encoded* length, before the decode
    # call allocates a buffer for the full decoded size. Base64 inflates
    # size by ~4/3, so an encoded-length bound corresponds to a slightly
    # larger decoded bound -- checked deliberately conservative (encoded
    # length, not the tighter estimated decoded length) so the rejection
    # happens strictly before base64.b64decode ever runs, per the "before
    # decode" requirement, with no dependence on decode succeeding first.
    max_encoded_chars = (_MAX_IMAGE_BASE64_BYTES * 4 + 2) // 3
    if len(image_base64) > max_encoded_chars:
        raise ToolError(
            f"image_base64 is too large: encoded length "
            f"{len(image_base64):,} chars exceeds the "
            f"{_MAX_IMAGE_BASE64_BYTES:,}-byte decoded-size limit"
        )

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
