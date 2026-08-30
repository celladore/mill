"""
Mill - document and media conversion

The xtox import and xtotext distribution names remain compatibility APIs.
"""

__version__ = "1.0.0"
__author__ = "Celladore"

if __package__:
    from .core import DocumentConverter, ImageConverter, MultiDocumentProcessor
    from .workflows import process_markdown_to_docx, process_markdown_to_pdf

    __all__ = [
        "DocumentConverter",
        "ImageConverter",
        "MultiDocumentProcessor",
        "process_markdown_to_docx",
        "process_markdown_to_pdf",
    ]
else:
    __all__ = []
