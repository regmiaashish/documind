"""Input validation covers disguised binaries, unreadable PDFs, and page metadata."""

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from documind.exceptions import AppError
from documind.services.parsing import parse_file, validate_file

SAMPLE = Path(__file__).resolve().parents[2] / "data/sample/handbook.pdf"


@pytest.mark.parametrize(
    "name,mime,data,code",
    [
        ("file.exe", "application/octet-stream", b"binary", "unsupported_file"),
        ("file.pdf", "application/pdf", b"MZbinary", "invalid_pdf"),
        ("file.txt", "text/plain", b"", "empty_file"),
        ("file.txt", "image/png", b"content", "unsupported_file"),
        ("file.txt", "text/plain", b"a" * (10 * 1024 * 1024 + 1), "file_too_large"),
    ],
)
def test_file_validation(name, mime, data, code):
    with pytest.raises(AppError) as caught:
        validate_file(name, mime, data)
    assert caught.value.code == code


@pytest.mark.parametrize(
    "data,code", [(b"\xff", "invalid_text"), (b"MZ\x00binary", "invalid_text"), (b" \n", "no_text")]
)
def test_text_rejections(data, code):
    with pytest.raises(AppError) as caught:
        parse_file(data, "text/plain")
    assert caught.value.code == code


def test_text_bom_and_filename():
    assert validate_file("../../policy.TXT", "text/plain", b"policy") == (
        "policy.TXT",
        "text/plain",
    )
    assert parse_file(b"\xef\xbb\xbfpolicy", "text/plain") == ([(None, "policy")], None)


def test_sample_pdf_keeps_pages_and_policy():
    pages, count = parse_file(SAMPLE.read_bytes(), "application/pdf")
    assert count == 3
    assert [number for number, _ in pages] == [1, 2, 3]
    assert "20 days" in pages[0][1]


@pytest.mark.parametrize("encrypted,code", [(True, "encrypted_pdf"), (False, "no_text")])
def test_encrypted_and_scanned_pdf(encrypted, code):
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    if encrypted:
        writer.encrypt("password")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(AppError) as caught:
        parse_file(stream.getvalue(), "application/pdf")
    assert caught.value.code == code


def test_malformed_pdf_has_safe_error():
    with pytest.raises(AppError) as caught:
        parse_file(b"%PDF-1.7\nbroken", "application/pdf")
    assert caught.value.code == "invalid_pdf"
