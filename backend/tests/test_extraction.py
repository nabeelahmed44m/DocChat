"""Tests for the extraction layer and dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import (
    EmptyDocumentError,
    UnsupportedFormatError,
)
from app.services.extraction import extract, supported_extensions


def test_supported_extensions_include_core_formats():
    exts = supported_extensions()
    assert ".txt" in exts
    assert ".pdf" in exts
    assert ".docx" in exts


def test_extract_text_document(sample_contract_path: Path):
    doc = extract(sample_contract_path)
    assert doc.mime_type == "text/plain"
    assert doc.page_count == 1
    assert "Service Agreement" in doc.full_text
    # Page offsets must index back into full_text.
    page = doc.pages[0]
    assert doc.full_text[page.char_start : page.char_end].strip()


def test_unsupported_format_raises(tmp_path: Path):
    weird = tmp_path / "thing.xyz"
    weird.write_text("hello")
    with pytest.raises(UnsupportedFormatError):
        extract(weird)


def test_empty_document_raises(tmp_path: Path):
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n  \t ")
    with pytest.raises(EmptyDocumentError):
        extract(empty)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        extract(tmp_path / "nope.txt")


def test_hard_wrapped_text_is_rejoined(tmp_path: Path):
    wrapped = tmp_path / "wrapped.txt"
    wrapped.write_text(
        "The notice period is sixty\ndays from the date of\nwritten notice.\n\n"
        "A new paragraph begins here."
    )
    doc = extract(wrapped)
    # Single newlines within a paragraph collapse to spaces...
    assert "sixty days from the date of written notice." in doc.full_text
    # ...but the paragraph break is preserved.
    assert "\n\n" in doc.full_text


def test_pdf_extraction_roundtrip(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "generated.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "The retainer is $12,500 per month.")
    doc.save(pdf_path)
    doc.close()

    result = extract(pdf_path)
    assert result.mime_type == "application/pdf"
    assert result.page_count == 1
    assert "12,500" in result.full_text


def test_docx_extraction_roundtrip(tmp_path: Path):
    docx = pytest.importorskip("docx")
    docx_path = tmp_path / "generated.docx"
    document = docx.Document()
    document.add_paragraph("The governing law is Delaware.")
    document.save(docx_path)

    result = extract(docx_path)
    assert "Delaware" in result.full_text
