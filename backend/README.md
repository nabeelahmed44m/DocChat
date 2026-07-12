# Doc Chat — Backend (Phases 1–2)

Classical-NLP document question answering. **No LLMs**: every answer is a
verbatim span of the source document with a page citation, so there is zero
hallucination and the whole thing runs offline.

Phase 1 delivered the core engine + CLI. **Phase 2 adds the HTTP API**: upload
any document, poll processing status, and ask questions — the surface the React
Native app (Phase 3) will call.

## What works today

- **Any-format ingestion** via a dispatcher: PDF (PyMuPDF), DOCX (python-docx),
  PPTX (python-pptx), XLSX (openpyxl), TXT/MD/CSV, **images/scans via OCR**
  (Tesseract), and legacy .doc/.rtf/.odt via a **LibreOffice** fallback. New
  formats = one `BaseExtractor` subclass.
- **Classical NLP**: regex tokenizer with stopword removal + Snowball stemming;
  sentence segmentation (pysbd, regex fallback) with source offsets; overlapping
  passage windows.
- **Hybrid extractive QA**: BM25 (sparse) + TF-IDF cosine + **LSA** (latent-
  semantic dense retrieval via TruncatedSVD — synonymy-aware, still no LLM), with
  regex/NER answer-typing (dates for "when", money for "how much", …).
- Answers carry **page number + exact character offsets** for later highlighting.
- **REST API** with background ingestion, status polling, and persistence.
- **Multi-document search**, optional **API-key auth** with per-owner isolation,
  and a **pluggable store** (JSON file or SQL / SQLite / Postgres).

## Architecture

```
app/
├── core/            config (env-driven), logging, exceptions
├── models/          Document, Page, Sentence, Passage, Answer, DocumentRecord
├── services/
│   ├── extraction/  dispatcher + pdf/docx/image(OCR)/text extractors
│   ├── nlp/         preprocess (tokenize) + segmentation (sentences, passages)
│   ├── qa/          hybrid index (BM25 + TF-IDF + LSA) + engine (extractive answering)
│   ├── analysis/    summarize (TextRank+MMR) · keypoints (RAKE + rules) · tables (pdfplumber)
│   ├── storage/     BaseDocumentStore + JSON and SQL backends (pluggable via config)
│   └── ingestion/   IngestionService (background thread-pool processing)
├── api/             FastAPI app factory, routes, schemas, error handlers, deps
├── pipeline.py      extract → analyze → index → engine
├── cli.py           info / ask / chat commands
└── main.py          uvicorn ASGI entry point
tests/               extraction, nlp, end-to-end QA, and API integration tests
```

Each layer depends only on the ones beneath it and on `models/`, so the API and
ingestion worker reuse `ingest()` unchanged.

## API

Run it:

```bash
uvicorn app.main:app --reload            # dev, http://127.0.0.1:8000
# interactive docs at /docs
```

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Liveness + capabilities (supported formats, OCR availability) |
| POST | `/documents` | Upload a file (multipart) → `202` with a `queued` record |
| GET  | `/documents` | List documents |
| GET  | `/documents/{id}` | Full record |
| GET  | `/documents/{id}/status` | Lightweight status for polling |
| POST | `/documents/{id}/ask` | `{question, top_k}` → ranked answers with citations |
| GET  | `/documents/{id}/summary` | Extractive summary (TextRank + MMR), `?max_sentences=N` |
| GET  | `/documents/{id}/keypoints` | Keyphrases (RAKE) + rule-based domain highlights |
| GET  | `/documents/{id}/tables` | Tables extracted from a PDF (pdfplumber) |
| POST | `/search` | Ask across all your documents; ranked results with attribution |
| DELETE | `/documents/{id}` | Delete a document |

When `DOCCHAT_API_KEYS` is set, pass `Authorization: Bearer <key>` (or
`X-API-Key: <key>`); documents are then isolated per key. With no keys set, auth
is off and everything runs as a single `public` tenant.

Lifecycle: `POST /documents` returns immediately; the file is processed on a
background thread pool (`queued → processing → ready`/`failed`). The client polls
`/status`, then calls `/ask`. Answers include `page_number`, `char_start/end`,
and a `citation` so the app can jump to and highlight the source.

```bash
# Example
curl -F "file=@contract.pdf" http://127.0.0.1:8000/documents        # -> {id, status:"queued"}
curl http://127.0.0.1:8000/documents/<id>/status                    # -> {status:"ready", stats:{...}}
curl -X POST http://127.0.0.1:8000/documents/<id>/ask \
     -H 'Content-Type: application/json' \
     -d '{"question":"What is the termination notice period?","top_k":3}'
```

## Setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Usage

```bash
# Ingestion stats
python -m app.cli info tests/data/sample_contract.txt

# One-shot question
python -m app.cli ask tests/data/sample_contract.txt "What is the termination notice period?"

# Interactive chat over a document (try a PDF or DOCX too)
python -m app.cli chat /path/to/your/contract.pdf
```

## Tests

```bash
pytest              # from backend/
pytest --cov=app    # with coverage
```

## Configuration

All knobs are environment variables (prefix `DOCCHAT_`); see `.env.example`.
Notable: `PASSAGE_WINDOW`, `PASSAGE_STRIDE`, `TOP_K_PASSAGES`, `TOP_K_ANSWERS`,
`BM25_WEIGHT`, `TFIDF_WEIGHT`.

## Design notes

- **Why extractive?** No LLM means we retrieve-and-quote rather than generate.
  For lawyers/accountants this is a feature: cite-able, verifiable answers.
- **Graceful degradation**: if `rank_bm25`, `scikit-learn`, or `pysbd` are
  missing, self-contained fallbacks keep the engine working (lower quality).
- **Offsets everywhere**: extraction computes global character offsets once, so
  every sentence/answer can be located — and later highlighted — in the source.

## Docker

```bash
docker build -t docchat-backend .
docker run -p 8000:8000 -v "$PWD/data:/app/data" docchat-backend
```

The image installs the `tesseract-ocr` binary so the OCR path works out of the
box. `data/` is a volume so uploaded documents and the registry persist.

## Roadmap

- **Phase 2** ✅: FastAPI (`POST /documents`, `GET /documents/{id}/status`,
  `POST /documents/{id}/ask`), background processing, OCR for scans/images.
- **Phase 3** ✅: React Native (Expo) mobile app — upload/camera, chat, citations.
- **Phase 4** ✅: summaries (TextRank+MMR), key-point highlights (RAKE + domain
  rules), table extraction (pdfplumber).
- **Phase 5** ✅: hybrid dense retrieval (LSA), multi-document search, API-key
  auth with per-owner isolation, pluggable SQL store (SQLite/Postgres), and more
  formats (PPTX, XLSX, legacy .doc/.rtf/.odt via LibreOffice).
