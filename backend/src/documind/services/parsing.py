"""Validate PDF/text bytes and extract page-aware text without OCR."""

import unicodedata
from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from documind.core.config import settings
from documind.exceptions import AppError


def validate_file(filename: str | None, content_type: str | None, data: bytes) -> tuple[str, str]:
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    if not name or len(name) > 255 or any(ord(c) < 32 for c in name):
        raise AppError(400, "invalid_filename", "Provide a filename of at most 255 characters.")
    suffix = PurePosixPath(name).suffix.lower()
    expected = {".pdf": "application/pdf", ".txt": "text/plain"}.get(suffix)
    if expected is None or content_type not in (expected, "application/octet-stream", None):
        raise AppError(415, "unsupported_file", "Upload a PDF or UTF-8 .txt file.")
    if not data:
        raise AppError(400, "empty_file", "The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise AppError(413, "file_too_large", "Files must be 10 MB or smaller.")
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise AppError(400, "invalid_pdf", "This file is not a valid PDF.")
    return name, expected


def parse_file(data: bytes, content_type: str) -> tuple[list[tuple[int | None, str]], int | None]:
    if content_type == "text/plain":
        try:
            pages = [(None, data.decode("utf-8-sig"))]
        except UnicodeDecodeError as error:
            raise AppError(400, "invalid_text", "Text files must use UTF-8 encoding.") from error
        page_count = None
    else:
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise AppError(400, "encrypted_pdf", "Upload a PDF without password protection.")
            page_count = len(reader.pages)
            if page_count > settings.max_pdf_pages:
                raise AppError(413, "too_many_pages", "PDFs must have 100 pages or fewer.")
            pages = []
            total = 0
            for number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                total += len(text)
                if total > settings.max_extracted_characters:
                    raise AppError(
                        413, "too_much_text", "Extracted text exceeds 500,000 characters."
                    )
                pages.append((number, text))
        except (PdfReadError, ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
            raise AppError(
                400, "invalid_pdf", "The PDF cannot be read. Upload a valid PDF."
            ) from error
    if sum(len(text) for _, text in pages) > settings.max_extracted_characters:
        raise AppError(413, "too_much_text", "Extracted text exceeds 500,000 characters.")
    if any(
        unicodedata.category(char) == "Cc" and char not in "\n\r\t\f"
        for _, text in pages
        for char in text
    ):
        raise AppError(400, "invalid_text", "The file contains unsupported binary characters.")
    if not any(text.strip() for _, text in pages):
        raise AppError(400, "no_text", "No readable text found. Scanned PDFs need OCR first.")
    return pages, page_count
