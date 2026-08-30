"""Compatibility bridge from xtox.workflows to workflows."""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[2] / "workflows")]

from .md_to_docx import process_markdown_to_docx  # noqa: E402
from .md_to_pdf import process_markdown_to_pdf  # noqa: E402

__all__ = ["process_markdown_to_pdf", "process_markdown_to_docx"]
