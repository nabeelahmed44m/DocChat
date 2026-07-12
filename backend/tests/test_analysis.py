"""Tests for Phase 4 analysis: summarize, key points, tables."""

from __future__ import annotations

import pytest

from app.services.analysis import extract_key_points, extract_tables, summarize


def test_summary_returns_ordered_verbatim_sentences(contract_result):
    doc = contract_result.document
    summary = summarize(doc, max_sentences=4)

    assert summary.method == "textrank+mmr"
    assert 0 < len(summary.sentences) <= 4
    # Every summary sentence is verbatim and correctly located.
    for s in summary.sentences:
        assert doc.full_text[s.char_start : s.char_end] == s.text
    # Sentences are presented in reading order.
    orders = [s.order for s in summary.sentences]
    assert orders == sorted(orders)
    # Ranks are a permutation of 0..n-1.
    assert sorted(s.rank for s in summary.sentences) == list(range(len(summary.sentences)))


def test_summary_short_doc_not_over_truncated(contract_result):
    summary = summarize(contract_result.document, max_sentences=100)
    # Asking for more sentences than exist just returns what's there.
    assert len(summary.sentences) <= summary.source_sentence_count


def test_keyphrases_surface_domain_terms(contract_result):
    kp = extract_key_points(contract_result.document)
    assert kp.keyphrases
    joined = " ".join(kp.keyphrases).lower()
    # RAKE should surface multi-word domain phrases from the contract.
    assert any(term in joined for term in ("consultant", "agreement", "confidential", "client"))


def test_keypoints_categorize_money_and_obligations(contract_result):
    kp = extract_key_points(contract_result.document)
    categories = {p.category for p in kp.points}
    # The sample contract has monetary amounts and "shall" obligations.
    assert "monetary" in categories or any("$12,500" in " ".join(p.highlights) for p in kp.points)
    assert "obligation" in categories
    # Every key point is verbatim + carries a citation-able page.
    doc = contract_result.document
    for p in kp.points:
        assert doc.full_text[p.char_start : p.char_end] == p.text
        assert p.page_number >= 1


def test_keypoints_include_termination_clause(contract_result):
    kp = extract_key_points(contract_result.document)
    texts = " ".join(p.text.lower() for p in kp.points)
    assert "terminat" in texts


def test_tables_on_non_pdf_returns_note(sample_contract_path):
    result = extract_tables(sample_contract_path, "text/plain")
    assert result.engine == "none"
    assert result.tables == ()
    assert result.note and "PDF" in result.note


def test_tables_extracted_from_generated_pdf(tmp_path):
    fitz = pytest.importorskip("fitz")
    pytest.importorskip("pdfplumber")
    pdf_path = tmp_path / "table.pdf"

    # Draw a simple ruled 2x3 table so pdfplumber's line strategy detects it.
    doc = fitz.open()
    page = doc.new_page()
    rows = [["Item", "Qty", "Price"], ["Widget", "10", "$5.00"], ["Gadget", "3", "$9.50"]]
    x0, y0, cell_w, cell_h = 72, 72, 120, 28
    shape = page.new_shape()
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            x = x0 + c * cell_w
            y = y0 + r * cell_h
            shape.draw_rect(fitz.Rect(x, y, x + cell_w, y + cell_h))
            page.insert_text((x + 6, y + 18), value, fontsize=11)
    shape.finish(color=(0, 0, 0), width=0.8)
    shape.commit()
    doc.save(pdf_path)
    doc.close()

    result = extract_tables(pdf_path, "application/pdf")
    assert result.engine == "pdfplumber"
    assert result.tables, result.note
    table = result.tables[0]
    assert table.page_number == 1
    flat = " ".join(cell for row in (table.header,) + table.rows for cell in row)
    assert "Widget" in flat and "Gadget" in flat
