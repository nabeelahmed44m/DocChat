"""Terminal interface for Phase 1.

Two modes:

* ``ask`` a single question and print answers (scriptable).
* ``chat`` — an interactive REPL over one document.

This proves the whole product works before the API and mobile app exist.

Examples::

    python -m app.cli ask path/to/contract.pdf "What is the termination notice period?"
    python -m app.cli chat path/to/report.docx
    python -m app.cli info path/to/manual.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.exceptions import DocChatError
from app.core.logging import configure_logging
from app.pipeline import IngestResult, ingest


def _print_answers(question: str, result: IngestResult, top_k: int) -> None:
    answers = result.engine.answer(question, top_k=top_k)
    if not answers:
        print("  No relevant passage found.")
        return
    for rank, ans in enumerate(answers, start=1):
        print(f"\n  [{rank}] (score {ans.score:.3f} · {ans.citation()})")
        print(f"      {ans.text}")
        if ans.matched_entities:
            print(f"      ↳ matched: {', '.join(ans.matched_entities)}")


def _cmd_info(args: argparse.Namespace) -> int:
    result = ingest(args.file)
    print(f"\nDocument: {result.document.filename}")
    print(f"MIME:     {result.document.mime_type}")
    for key, value in result.stats.items():
        print(f"  {key:12s}: {value}")
    print(f"  {'ingest time':12s}: {result.elapsed_seconds:.2f}s")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    result = ingest(args.file)
    print(f"\nQ: {args.question}")
    _print_answers(args.question, result, args.top_k)
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    result = ingest(args.file)
    print(
        f"\nLoaded '{result.document.filename}' "
        f"({result.stats['sentences']} sentences, {result.stats['pages']} page(s)). "
        "Ask a question, or type 'exit'."
    )
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"exit", "quit", ":q"}:
            break
        if not question:
            continue
        _print_answers(question, result, args.top_k)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docchat",
        description="Classical-NLP document question answering (no LLMs).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show pipeline logs"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="show ingestion stats for a document")
    p_info.add_argument("file", type=Path)
    p_info.set_defaults(func=_cmd_info)

    p_ask = sub.add_parser("ask", help="ask one question and exit")
    p_ask.add_argument("file", type=Path)
    p_ask.add_argument("question")
    p_ask.add_argument("-k", "--top-k", type=int, default=3)
    p_ask.set_defaults(func=_cmd_ask)

    p_chat = sub.add_parser("chat", help="interactive Q&A over a document")
    p_chat.add_argument("file", type=Path)
    p_chat.add_argument("-k", "--top-k", type=int, default=3)
    p_chat.set_defaults(func=_cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging("INFO" if args.verbose else "WARNING")
    try:
        return args.func(args)
    except DocChatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
