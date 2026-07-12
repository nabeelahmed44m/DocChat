# Doc Chat — Research & Build Plan (Classical NLP, No LLMs)

**Goal:** A **mobile app** where any user uploads **any document** (PDF, Word, scanned image, text…) and asks questions about it. Core feature is Q&A; summaries, tables, and key-point highlighting are secondary.

## 0. Universal document ingestion

All formats are normalized to one internal representation (plain text + sentence offsets + page/section markers) before the NLP pipeline runs:

| Format | Extractor |
|---|---|
| PDF (digital) | PyMuPDF |
| PDF (scanned) / photos (JPG/PNG) | ocrmypdf / Tesseract → text |
| DOCX | python-docx (or `mammoth` → HTML) |
| PPTX | python-pptx |
| XLSX/CSV | pandas (sheet → row-wise text) |
| TXT / Markdown / HTML | direct / BeautifulSoup |
| Legacy .doc, RTF, ODT | LibreOffice headless convert → DOCX/PDF first |

One dispatcher (`extract(file) -> Document`) picks the extractor by MIME type; everything downstream (BM25, TextRank, NER) is format-agnostic because it only sees the normalized text. Use **Apache Tika** as a single fallback extractor for anything exotic.

## 0.1 Mobile app architecture

The NLP stack (spaCy, BM25, Camelot…) is Python and too heavy for on-device use, so the phone is a thin client and all processing happens on the server:

```
Mobile app (React Native / Flutter)
  ├─ pick/upload document (camera scan, files app, share-sheet "Open with…")
  ├─ chat screen per document
  └─ document viewer with highlighted answer
        │ HTTPS/JSON
FastAPI backend  →  ingestion worker  →  BM25/vector index per document
```

- **Recommended: React Native + Expo** — one codebase for iOS/Android, `expo-document-picker` + camera for uploads, and if you ever want a web app it's the same code. **Flutter** is an equally good choice if you prefer Dart.

### Frontend stack (researched July 2026 — see §7 for the full comparison)

| Concern | Choice | Why |
|---|---|---|
| Design system / components | **Tamagui** | Compiler-optimized, 60fps native + web, fully themeable → a *distinctive* look, not a templated Material clone. Best fit for a long-lived product with its own design language. |
| Fast-start alternative | Gluestack UI | Copy-paste, Tailwind-like props, "install and go" — pick this instead if we want the first sprint done fastest. |
| Animations (core) | **React Native Reanimated 4** | Runs on the UI thread at up to 120fps; the production standard (Shopify, Expo). Powers gesture-driven chat + viewer transitions. |
| Animation ergonomics | **Moti** | Declarative wrapper over Reanimated for one-line entrance/spring animations. |
| Loaders / empty states | **Lottie** (`lottie-react-native`) | Polished loading + "processing your document" animations. |
| Bottom sheets / modals | **@gorhom/bottom-sheet** | The de-facto native-feeling sheet for upload picker & citations. |
| Chat list | **FlashList** (Shopify) | High-performance message list — smooth even with long transcripts. |
| Navigation | **Expo Router** | File-based routing, deep links, share-sheet targets. |
| Upload / camera | **expo-document-picker + expo-image-picker + expo-camera + expo-file-system** | Any file from Files/Drive/iCloud, plus the camera-scan flow. |
| Icons | **lucide-react-native** | Clean, consistent, modern icon set. |

Design direction: dark-first, high-contrast, generous whitespace, one strong accent color, and answer cards that show the quoted sentence with a "jump to page N" chip — matching the confident, professional aesthetic in the reference screenshot.
- Upload → server returns a document ID and processing status; the app polls (or uses a WebSocket) until "ready", then the chat is enabled.
- Answers return with page number + character offsets so the app can scroll the viewer to the quoted sentence.
- Camera "scan a paper document" flow = photos → server OCR → same pipeline. This is a killer mobile feature and costs almost nothing extra.

---

**Original per-feature research follows** (still accurate — Q&A is section 1.1):

1. Ask questions and get answers
2. Get summaries
3. Extract tables
4. See key points highlighted

**Hard constraint:** No LLMs. Everything is built from classical/statistical NLP: tokenization, TF-IDF, embeddings (word/sentence vectors), extractive algorithms, rule-based parsing, and small pretrained encoder models at most.

---

## 1. How each feature works without an LLM

### 1.1 Question Answering → **Extractive QA (retrieve + rank), not generative**

You cannot generate free-form answers without an LLM, so the system *finds* the answer span/sentence in the document instead of writing one. This is actually a selling point for lawyers/accountants: every answer is a verbatim quote with a page citation — zero hallucination.

Pipeline:
1. **Ingest:** extract text per page, keep character offsets and page numbers.
2. **Segment:** split into sentences (spaCy / NLTK Punkt) and group into overlapping passages (~3–5 sentences).
3. **Index (hybrid retrieval):**
   - **Sparse:** BM25 (rank_bm25 or Elasticsearch/OpenSearch). Great for exact legal/financial terms ("Section 7.2", "indemnification").
   - **Dense (optional but recommended):** sentence embeddings via `sentence-transformers` (e.g. `all-MiniLM-L6-v2`) + FAISS. Note: this is a small BERT-family *encoder* — it embeds text, it does not generate. If you want to be strictly "no neural nets at all," use TF-IDF cosine similarity or LSA (TruncatedSVD) instead.
4. **Query processing:** tokenize, lemmatize, expand with WordNet synonyms; detect question type (who/when/how much) with simple rules.
5. **Answer selection:** rank passages by combined BM25 + cosine score; within the top passage, pick the best sentence. For "who/when/how much" questions, run NER (spaCy) and prefer sentences containing the matching entity type (PERSON, DATE, MONEY).
6. **Return:** the sentence(s) + page number + surrounding context, highlighted in the PDF viewer.

### 1.2 Summarization → **Extractive summarization**

Pick the most important sentences; never rewrite text (again a feature for legal — no paraphrase risk).

- **TextRank / LexRank:** build a graph of sentences, edges = similarity (TF-IDF cosine), run PageRank, take top-N. Libraries: `sumy`, or `networkx` + scikit-learn by hand.
- **LSA summarization** (sumy has it) as an alternative.
- **MMR (Maximal Marginal Relevance)** on top to reduce redundancy in the selected sentences.
- Offer per-section summaries (detect headings via font size/boldness from the PDF layout) and a whole-document summary.

### 1.3 Table extraction → **Not NLP — layout/geometry parsing**

- **Camelot** (lattice mode for ruled tables, stream mode for whitespace-aligned) and **pdfplumber** as the fallback/second engine. Run both, pick the one with the better accuracy score.
- Export to CSV/XLSX (pandas), preview as HTML in the UI.
- For scanned PDFs: OCR first (Tesseract via `ocrmypdf`), then table detection gets harder — v2 feature.

### 1.4 Key point highlighting → **Keyphrase + salient sentence extraction**

- **Keyphrases:** YAKE! or KeyBERT-style TF-IDF/embedding ranking; RAKE as a simple baseline.
- **Salient sentences:** reuse TextRank scores; sentences above a percentile threshold get highlighted.
- **Domain rules (big differentiator for the target market):** regex/rule patterns for legal & financial hotspots — dates, deadlines, monetary amounts, percentages, party names, obligation language ("shall", "must", "is required to"), termination/liability/indemnity clauses. spaCy `Matcher`/`EntityRuler` is perfect for this.
- Render highlights directly on the PDF (PyMuPDF can add highlight annotations at exact coordinates since we kept offsets).

---

## 2. Recommended stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | The entire classical-NLP ecosystem lives here |
| PDF text + coordinates | **PyMuPDF (fitz)** | Fast, gives per-word bounding boxes → enables in-PDF highlighting |
| Tables | **Camelot + pdfplumber** | Two engines cover both ruled and whitespace tables |
| OCR (scanned docs) | **ocrmypdf / Tesseract** | Free, standard |
| NLP core | **spaCy** (`en_core_web_sm/md`) | Sentence split, lemmas, POS, NER, rule Matcher |
| Sparse retrieval | **BM25** — `rank_bm25` (in-process) now, Elasticsearch later | QA backbone |
| Dense retrieval (optional) | **sentence-transformers MiniLM + FAISS** | Better recall on paraphrased questions; still not an LLM |
| Summarization | **sumy** (TextRank/LexRank/LSA) or custom networkx | Extractive, cite-able |
| Keyphrases | **YAKE** / RAKE | Unsupervised, no training data needed |
| API backend | **FastAPI** | Async, file uploads, easy background jobs |
| Job queue | **Celery + Redis** (or FastAPI BackgroundTasks for MVP) | PDF processing is slow; don't block requests |
| Metadata DB | **PostgreSQL** (SQLite for MVP) | Docs, chats, users |
| Frontend | **React + pdf.js** (e.g. `react-pdf`) | Render PDF with highlight overlays; chat panel beside it |
| Packaging | **Docker** | Reproducible deploys |

Strictest "no neural anything" variant: drop sentence-transformers/FAISS, use TF-IDF + LSA (scikit-learn) for dense-ish matching. Everything else stays the same.

---

## 3. Architecture

```
                ┌──────────────────────────────┐
   Upload PDF → │ FastAPI                      │
                │  /upload  /ask  /summary     │
                │  /tables  /keypoints         │
                └──────┬───────────────────────┘
                       │ enqueue
                ┌──────▼───────────────────────┐
                │ Ingestion worker (Celery)     │
                │ 1. PyMuPDF text + coords      │
                │ 2. (OCR if scanned)           │
                │ 3. spaCy sentences/NER        │
                │ 4. Build BM25 + vector index  │
                │ 5. Precompute TextRank, YAKE, │
                │    tables (Camelot)           │
                └──────┬───────────────────────┘
                       │ store
        ┌──────────────┼──────────────┐
        │ PostgreSQL   │ FAISS/index  │ object storage (PDFs)
        └──────────────┴──────────────┘

   React UI: PDF viewer (pdf.js) + chat sidebar + tables tab + key-points overlay
```

Everything per-feature is **precomputed at upload time** except QA, which runs per question (fast: BM25 + cosine over an in-memory index).

---

## 4. Build roadmap

**Phase 1 — Ingestion + QA core (weeks 1–2)**
Python scripts only: multi-format `extract()` dispatcher (PDF, DOCX, TXT first) → normalized text with offsets → sentence segmentation → BM25 index → answer questions in the terminal. This proves the whole product.

**Phase 2 — API (week 3)**
FastAPI: `POST /documents` (any file type), `GET /documents/{id}/status`, `POST /documents/{id}/ask`. Background processing via Celery/BackgroundTasks. Add OCR path for images/scans.

**Phase 3 — Mobile app MVP (weeks 4–6)**
React Native (Expo): upload from files/camera, processing status, chat screen with answers + page citations. Ship to TestFlight/internal testing.

**Phase 4 — Secondary features (weeks 7–8)**
Summaries (TextRank), key-point highlights, table extraction tab; in-app document viewer that scrolls to the answer.

**Phase 5 — Hardening (ongoing)**
Hybrid dense retrieval, multi-document search, user accounts, remaining formats via Tika/LibreOffice.

---

## 5. Evaluation plan (this is the "research" part)

- **QA:** build a small gold set — 50–100 (question, answer-sentence, page) triples over 10 real documents. Metrics: MRR and answer-sentence recall@3. Compare BM25 alone vs BM25+TF-IDF vs BM25+MiniLM.
- **Summarization:** ROUGE-1/2/L against reference summaries (or human 1–5 ratings on informativeness/redundancy). Compare TextRank vs LexRank vs LSA.
- **Tables:** cell-level precision/recall on 20 annotated tables; Camelot vs pdfplumber vs both-combined.
- **Keypoints:** precision@10 of highlighted items judged by a domain reader.

## 6. Known limitations to state honestly

- Answers are quotes, not synthesized prose — cannot combine facts across paragraphs into one written answer.
- Summaries can feel choppy (extracted sentences lack connective flow).
- Complex multi-hop questions ("compare clause 4 with clause 9") are out of scope.
- Scanned/low-quality PDFs depend entirely on OCR quality.

These trade-offs buy you: full offline/on-prem operation (huge for legal confidentiality), zero hallucination, per-answer citations, and near-zero inference cost.

---

## 7. Frontend library research (July 2026)

**Component / design systems considered**

- **Tamagui** — compiler flattens components to atomic CSS on web and plain Views on native; 60fps, New-Architecture (Fabric/TurboModules) ready, fully themeable. Cost is a steeper setup. Best when you want a bespoke, long-lived design language. **→ chosen.**
- **Gluestack UI** — unstyled, accessible, universal components styled with Tailwind-like props; "copy-paste, you own the code," fastest first sprint. Strong fallback if timeline beats bespoke styling.
- **React Native Paper** — best-in-class Material Design 3 + accessibility, but looks like stock Android/Material, which works against "eye-catching and distinctive."
- Also-rans: React Native Elements, UI Kitten (Eva design), NativeBase — solid but less differentiated in 2026.

**Animation** — Reanimated 4 is the production standard (UI-thread, up to 120fps, used by Shopify/Expo); real apps combine Reanimated for interactions, Lottie for loaders/empty states, and shared-element transitions for detail screens. Moti sits on top for terse declarative animations.

**Uploads / chat** — `expo-document-picker` (Files/Drive/iCloud), `expo-image-picker` + `expo-camera` (scan-a-paper flow), `expo-file-system` for caching; Shopify **FlashList** for the message transcript.

**Sources**
- [Top React Native UI libraries in 2026 — DEV](https://dev.to/ninarao/top-react-native-ui-libraries-in-2026-2gbe)
- [The 10 best React Native UI libraries of 2026 — LogRocket](https://blog.logrocket.com/best-react-native-ui-component-libraries/)
- [Best React Native UI Libraries 2026: Tested & Ranked — Applighter](https://www.applighter.com/blog/react-native-ui-libraries)
- [Tamagui vs Gluestack UI vs UI Kitten — Axentix](https://useaxentix.com/blog/tamagui/tamagui-gluestack-ui-kitten-what-react-native-devs-say/)
- [React Native Reanimated docs](https://docs.swmansion.com/react-native-reanimated/)
- [I Tested 9 React Native Animation Libraries — F22 Labs](https://www.f22labs.com/blogs/9-best-react-native-animation-libraries/)
- [Expo DocumentPicker docs](https://docs.expo.dev/versions/latest/sdk/document-picker/)
