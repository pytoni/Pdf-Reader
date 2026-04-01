"""
pdf2markdown: A robust PDF-to-Markdown extraction library.
"""

from .core import (
    clean_text,
    extract_pages_with_pdfplumber,
    extract_text_with_pdfplumber,
    read_pdf,
    table_to_markdown,
    to_markdown_format,
)

__all__ = [
    "clean_text",
    "extract_pages_with_pdfplumber",
    "extract_text_with_pdfplumber",
    "read_pdf",
    "table_to_markdown",
    "to_markdown_format",
]
