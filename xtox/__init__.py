"""Compatibility namespace for the historical xtox Python import."""

from .core import DocumentConverter, ImageConverter, MultiDocumentProcessor
from .workflows import process_markdown_to_docx, process_markdown_to_pdf

__version__ = "1.0.0"
__all__ = [
    "DocumentConverter",
    "ImageConverter",
    "MultiDocumentProcessor",
    "process_markdown_to_docx",
    "process_markdown_to_pdf",
]
