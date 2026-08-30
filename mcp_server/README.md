# Mill image conversion — MCP server

A local stdio [MCP](https://modelcontextprotocol.io) server that exposes Mill's
Pillow-backed image conversion (`core/image_converter.py`) as tools any MCP
client can call — Claude Code, Claude Desktop, or another agent.

It runs entirely in-process against `core/image_converter.py`; it does not
call the deployed HTTP API (which sits behind Mystira OIDC auth). That keeps
it working offline and with no token setup.

## Tools

| Tool | Use when | Input | Output |
|---|---|---|---|
| `convert_image` | Client and server share a filesystem (e.g. Claude Code) | `input_path`, `target_format`, optional `output_path`/`quality`/`max_width`/`max_height` | JSON: output path, dimensions, size in KB |
| `convert_image_base64` | No shared filesystem (e.g. a chat client) | `image_base64`, `filename`, `target_format`, optional `quality` | Inline image content block + text summary |
| `get_image_info` | Inspect an image on disk | `path` | JSON: format, mode, dimensions, size in KB, has_transparency |
| `list_supported_formats` | Discover what's supported | — | JSON: formats and quality presets |

Supported formats: JPEG, PNG, WebP, BMP, TIFF, GIF (same allowlist as
`backend/utils/file_validator.py`'s `FileValidator.IMAGE_EXTENSIONS` and the
`POST /api/convert-image` endpoint). Quality presets: `high` (95), `medium`
(75), `low` (50), `web` (85).

## Setup

```bash
pip install -r mcp_server/requirements.txt
```

## Register with Claude Code

```bash
claude mcp add mill-images -- python /absolute/path/to/mill/mcp_server/server.py
```

Or add directly to `.mcp.json`:

```json
{
  "mcpServers": {
    "mill-images": {
      "command": "python",
      "args": ["/absolute/path/to/mill/mcp_server/server.py"]
    }
  }
}
```

Use the interpreter that has `mcp_server/requirements.txt` installed (a venv
path, e.g. `/absolute/path/to/mill/.venv/bin/python`, if you're not using the
system Python).

## Notes

- Validation failures (unsupported format, missing file, bad quality preset)
  raise `mcp.server.mcpserver.exceptions.ToolError` so the client sees the
  actual reason. Anything else is treated as a crash by the SDK and the
  client only sees "Error executing tool `<name>`" — check server stderr for
  the traceback in that case.
- `mcp_server/server.py` loads `core/image_converter.py` by file path rather
  than importing the `core` package, so it doesn't pull in the unrelated
  document converters (LaTeX/DOCX/HTML) and their dependencies. Same pattern
  as `backend/services/audio_service.py` and `backend/services/image_service.py`.
