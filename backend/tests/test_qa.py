"""End-to-end QA tests against the sample contract.

These assert the *right span* is retrieved for realistic professional questions
— the core promise of the product.
"""

from __future__ import annotations

import pytest


def _top_texts(result, question, k=3):
    return [a.text.lower() for a in result.engine.answer(question, top_k=k)]


def test_termination_notice_period(contract_result):
    answers = _top_texts(contract_result, "What is the termination notice period?")
    assert any("sixty (60) days" in a for a in answers)


def test_monthly_fee_amount(contract_result):
    answers = _top_texts(contract_result, "How much is the monthly retainer?")
    assert any("$12,500" in a for a in answers)


def test_governing_law(contract_result):
    answers = _top_texts(contract_result, "Which law governs this agreement?")
    assert any("delaware" in a for a in answers)


def test_when_question_prefers_dates(contract_result):
    answers = contract_result.engine.answer(
        "When does the agreement commence?", top_k=3
    )
    assert answers
    # The commencement date sentence should surface in the top results.
    assert any("february 1, 2024" in a.text.lower() for a in answers)


def test_answer_carries_valid_citation_and_offsets(contract_result):
    answers = contract_result.engine.answer("What is the liability cap?", top_k=1)
    assert answers
    ans = answers[0]
    doc = contract_result.document
    assert 1 <= ans.page_number <= doc.page_count
    assert doc.full_text[ans.char_start : ans.char_end] == ans.text
    assert ans.citation() == f"page {ans.page_number}"


def test_empty_question_returns_no_answers(contract_result):
    assert contract_result.engine.answer("   ") == []


def test_answer_serialization_roundtrip(contract_result):
    ans = contract_result.engine.answer("What is the governing law?", top_k=1)[0]
    payload = ans.to_dict()
    assert payload["text"] == ans.text
    assert payload["citation"] == ans.citation()
    assert isinstance(payload["matched_entities"], list)


@pytest.mark.parametrize(
    "question",
    [
        "What are the confidentiality obligations?",
        "Who are the parties to the agreement?",
        "What is the interest rate on late payments?",
    ],
)
def test_returns_some_answer_for_reasonable_questions(contract_result, question):
    assert contract_result.engine.answer(question, top_k=3)
