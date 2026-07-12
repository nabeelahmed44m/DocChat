"""Tests for the Phase 5 extractors (PPTX, XLSX) and format support."""

from __future__ import annotations

import pytest

from app.services.extraction import extract, supported_extensions


def test_supported_extensions_include_phase5_formats():
    exts = supported_extensions()
    for e in (".pptx", ".xlsx", ".doc", ".rtf", ".odt"):
        assert e in exts


def test_pptx_extraction(tmp_path):
    pptx = pytest.importorskip("pptx")
    path = tmp_path / "deck.pptx"

    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Quarterly Results"
    box = slide.shapes.add_textbox(0, 0, 400, 200)
    box.text_frame.text = "Revenue grew to $2.4 million in Q3."
    prs.save(path)

    doc = extract(path)
    assert doc.mime_type.endswith("presentationml.presentation")
    assert "Quarterly Results" in doc.full_text
    assert "2.4 million" in doc.full_text


def test_xlsx_extraction(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "data.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Fees"
    ws.append(["Service", "Amount"])
    ws.append(["Retainer", 12500])
    ws.append(["Late fee", "1.5%"])
    wb.save(path)

    doc = extract(path)
    assert doc.mime_type.endswith("spreadsheetml.sheet")
    assert "Retainer" in doc.full_text
    assert "12500" in doc.full_text
    assert "Fees" in doc.full_text
