"""Compatibility bridge from xtox.core to Mill's existing core package."""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[2] / "core")]

from .document_converter import DocumentConverter  # noqa: E402
from .html_to_markdown import convert_html_to_markdown  # noqa: E402
from .image_converter import ImageConverter  # noqa: E402
from .interactive_processor import InteractiveProcessor  # noqa: E402
from .latex_to_pdf import check_latex_structure, fix_latex_structure, latex_to_pdf  # noqa: E402
from .markdown_to_docx import convert_markdown_to_docx  # noqa: E402
from .markdown_to_html import convert_markdown_to_html  # noqa: E402
from .markdown_to_latex import convert_markdown_to_latex  # noqa: E402
from .multi_document_processor import MultiDocumentProcessor  # noqa: E402

__all__ = [
    "DocumentConverter",
    "ImageConverter",
    "InteractiveProcessor",
    "MultiDocumentProcessor",
    "check_latex_structure",
    "convert_html_to_markdown",
    "convert_markdown_to_docx",
    "convert_markdown_to_html",
    "convert_markdown_to_latex",
    "fix_latex_structure",
    "latex_to_pdf",
]
