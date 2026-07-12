"""Gemini Flash integration for Q&A, summarization, key-point extraction, and table detection.

All text generation is exposed in two forms: a blocking call returning the parsed
result, and a ``stream_*`` generator yielding raw text chunks as Gemini produces
them (used by the ``/stream`` API endpoints). The parse helpers are shared so a
streamed response can be parsed and cached once the stream completes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _client() -> tuple[genai.Client, str]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError(
            "DOCCHAT_GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )
    client = genai.Client(api_key=settings.gemini_api_key)
    return client, settings.gemini_model


def _ask_contents(
    passages: list[str],
    question: str,
    filename: str,
    history: list[dict] | None,
) -> list[types.Content]:
    ctx = "\n\n".join(f"[Passage {i + 1}]\n{p}" for i, p in enumerate(passages))

    system = (
        f'You are a document assistant for "{filename}". '
        "Answer using only the provided passages. "
        "Be concise — 2-4 sentences max. "
        "Write in plain text only: no asterisks, no markdown, no bullet symbols. "
        "If citing a passage, write it naturally like 'according to the document'. "
        "If the answer is not in the passages, say so briefly."
    )

    contents: list[types.Content] = []
    for msg in (history or []):
        role = "user" if msg.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    prompt = f"{system}\n\nDocument passages:\n{ctx}\n\nQuestion: {question}"
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
    return contents


# thinking_budget=0 disables hidden "thinking" tokens: they count toward
# max_output_tokens (silently truncating answers) and add seconds of latency
# before the first streamed chunk.
_NO_THINKING = types.ThinkingConfig(thinking_budget=0)

_ASK_CONFIG = types.GenerateContentConfig(
    temperature=0.1, max_output_tokens=1024, thinking_config=_NO_THINKING
)


def ask_with_context(
    passages: list[str],
    question: str,
    filename: str = "document",
    history: list[dict] | None = None,
) -> str:
    client, model = _client()
    contents = _ask_contents(passages, question, filename, history)
    response = client.models.generate_content(
        model=model, contents=contents, config=_ASK_CONFIG
    )
    answer = response.text or ""
    logger.info("Gemini answered %r (%d chars)", question[:60], len(answer))
    return answer


def stream_answer(
    passages: list[str],
    question: str,
    filename: str = "document",
    history: list[dict] | None = None,
) -> Iterator[str]:
    """Yield the answer to *question* chunk by chunk as Gemini generates it."""
    client, model = _client()
    contents = _ask_contents(passages, question, filename, history)
    for chunk in client.models.generate_content_stream(
        model=model, contents=contents, config=_ASK_CONFIG
    ):
        if chunk.text:
            yield chunk.text


def _summary_prompt(full_text: str, filename: str) -> str:
    return f"""Analyze this document. Respond in plain text only — no asterisks, no markdown, no bold.

SUMMARY:
[Write 2-3 sentences summarizing the document's main purpose and content.]

BULLET POINTS:
• [Key highlight 1]
• [Key highlight 2]
• [Key highlight 3]
• [Key highlight 4]
• [Key highlight 5]
• [Key highlight 6]

Document title: {filename}

Document content:
{full_text[:50000]}"""


_ANALYSIS_CONFIG = types.GenerateContentConfig(
    temperature=0.1, max_output_tokens=8192, thinking_config=_NO_THINKING
)


def parse_summary(text: str) -> dict:
    summary = ""
    bullets: list[str] = []

    if "SUMMARY:" in text:
        after = text.split("SUMMARY:", 1)[1]
        summary_part = after.split("BULLET POINTS:")[0] if "BULLET POINTS:" in after else after
        summary = summary_part.strip()

    if "BULLET POINTS:" in text:
        section = text.split("BULLET POINTS:", 1)[1].strip()
        for line in section.split("\n"):
            line = line.strip()
            if line and line[0] in "•-*":
                pt = re.sub(r"^[•\-\*]\s*", "", line).strip()
                if pt:
                    bullets.append(pt)

    return {"summary": summary or text[:400], "bullet_points": bullets}


def render_summary(cached: dict) -> str:
    """Rebuild the raw streamed text format from a cached parsed summary."""
    bullets = "\n".join(f"• {b}" for b in cached.get("bullet_points", []))
    return f"SUMMARY:\n{cached.get('summary', '')}\n\nBULLET POINTS:\n{bullets}"


def summarize_document(full_text: str, filename: str = "document") -> dict:
    client, model = _client()
    response = client.models.generate_content(
        model=model,
        contents=_summary_prompt(full_text, filename),
        config=_ANALYSIS_CONFIG,
    )
    return parse_summary(response.text or "")


def stream_summary(full_text: str, filename: str = "document") -> Iterator[str]:
    """Yield the raw SUMMARY:/BULLET POINTS: text chunk by chunk."""
    client, model = _client()
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=_summary_prompt(full_text, filename),
        config=_ANALYSIS_CONFIG,
    ):
        if chunk.text:
            yield chunk.text


def _keypoints_prompt(full_text: str, filename: str) -> str:
    return f"""Extract key information from this document in plain text only — no asterisks, no markdown, no bold formatting.

KEY POINTS:
• [Specific fact, number, date, or finding]
• [Another key point]
(list 8-12 points)

IMPORTANT TERMS:
term1, term2, term3, term4, term5
(5-8 important terms, comma-separated, no brackets)

Document title: {filename}

Document content:
{full_text[:50000]}"""


def parse_keypoints(text: str) -> dict:
    points: list[str] = []
    keyphrases: list[str] = []

    if "KEY POINTS:" in text:
        kp_section = text.split("KEY POINTS:", 1)[1]
        if "IMPORTANT TERMS:" in kp_section:
            kp_section = kp_section.split("IMPORTANT TERMS:")[0]
        for line in kp_section.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line[0] in "•-*" or (line[0].isdigit() and len(line) > 2 and line[1] in ".)"):
                pt = re.sub(r"^[•\-\*\d\.:\)]+\s*", "", line).strip()
                if pt:
                    points.append(pt)

    if "IMPORTANT TERMS:" in text:
        section = text.split("IMPORTANT TERMS:", 1)[1].strip()
        for line in section.split("\n"):
            line = line.strip()
            if line:
                keyphrases = [t.strip().strip("[]") for t in line.split(",") if t.strip()]
                break

    return {"points": points, "keyphrases": keyphrases}


def render_keypoints(cached: dict) -> str:
    """Rebuild the raw streamed text format from a cached parsed keypoints result."""
    points = "\n".join(f"• {p}" for p in cached.get("points", []))
    terms = ", ".join(cached.get("keyphrases", []))
    return f"KEY POINTS:\n{points}\n\nIMPORTANT TERMS:\n{terms}"


def extract_key_points(full_text: str, filename: str = "document") -> dict:
    client, model = _client()
    response = client.models.generate_content(
        model=model,
        contents=_keypoints_prompt(full_text, filename),
        config=_ANALYSIS_CONFIG,
    )
    return parse_keypoints(response.text or "")


def stream_keypoints(full_text: str, filename: str = "document") -> Iterator[str]:
    """Yield the raw KEY POINTS:/IMPORTANT TERMS: text chunk by chunk."""
    client, model = _client()
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=_keypoints_prompt(full_text, filename),
        config=_ANALYSIS_CONFIG,
    ):
        if chunk.text:
            yield chunk.text


def extract_tables_ai(full_text: str, filename: str = "document") -> dict:
    """Ask Gemini to find and structure genuine data tables in the document text."""
    client, model = _client()

    prompt = f"""Analyze this document and find ONLY genuine data tables.

A genuine table MUST have ALL of these:
1. Clear, meaningful column headers (not bullet points, not symbols)
2. At least 2 columns with real data
3. At least 2 rows of actual structured data
4. Data that makes sense in a grid format (like a schedule, price list, comparison, report, etc.)

Do NOT extract:
- Resume sections or skill lists
- Bullet point lists
- Navigation menus
- Fragmented text that happens to appear in columns
- Any layout that is NOT a real data table

For each genuine table found, return valid JSON:
[
  {{
    "title": "Descriptive title of what this table shows",
    "header": ["Column Header 1", "Column Header 2", "Column Header 3"],
    "rows": [
      ["value", "value", "value"],
      ["value", "value", "value"]
    ]
  }}
]

IMPORTANT:
- Return ONLY the raw JSON array, no explanation, no markdown
- If no genuine tables exist, return exactly: []
- Cell values must be complete, meaningful strings (not single characters or symbols)
- Maximum 30 rows per table

Document title: {filename}

Document content:
{full_text[:40000]}"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0, max_output_tokens=8192, thinking_config=_NO_THINKING
        ),
    )
    text = (response.text or "").strip()

    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        tables_data = json.loads(text[start:end]) if start >= 0 and end > start else []
    except (json.JSONDecodeError, ValueError):
        tables_data = []

    tables = []
    for t in tables_data:
        if not isinstance(t, dict):
            continue
        header = [str(h) for h in t.get("header", [])]
        rows = [[str(c) for c in row] for row in t.get("rows", []) if isinstance(row, list)]
        if header:
            tables.append({
                "page_number": 1,
                "header": header,
                "rows": rows,
                "n_rows": len(rows),
                "n_cols": len(header),
                "title": t.get("title", ""),
            })

    return {
        "engine": "gemini",
        "count": len(tables),
        "note": "Extracted by AI — layout may differ from original." if tables else "No tables found in this document.",
        "tables": tables,
    }
