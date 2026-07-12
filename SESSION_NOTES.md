# PDF Chat — Session Notes
**Date:** 2026-07-12  
**Stack:** FastAPI + Neon Postgres backend · Expo SDK 57 React Native mobile · Gemini AI · Cloudflare tunnel

---

## What was built

PDF Chat is a mobile app that lets you upload documents (PDF, DOCX, XLSX, TXT, CSV, images, …) and then:
- **Chat** with them via Gemini-powered Q&A (streaming)
- **Summarize** them (streaming, cached after first run)
- **Extract key points** (streaming, cached)
- **Extract tables** (Gemini-only, no local parsing)
- **Search** across all documents by exact phrase

Physical iOS device connects to the FastAPI backend through a Cloudflare tunnel.

---

## Round 1 — UI overhaul + core features

### UI redesign
- **Document cards** — pastel-tinted, rotating through 6 colours (`palette.cardTints`), filename + file-type badge pill, size/pages metadata, status pill + eye button
- **Bottom tab bar** — Docs / Search / Profile tabs with icons, themed tab bar
- **Purple FAB** for upload
- **StatusPill** — coloured dot (spinner for processing) + label, replaces old icon/uppercase pill

### Document viewer
- PDFs, images, Office files → WKWebView (native iOS engine, Preview-like pinch/zoom + continuous scroll)
- Text-like files (`.txt .md .csv .log`) → native `ScrollView` + themed monospace `Text` component (WKWebView rendered them unreadably pale)

### Tables — Gemini only
- Removed all `pdfplumber` local extraction
- `extract_tables_ai()` gives the full document text to Gemini and asks it to find genuine data tables only
- Returns `{engine:'gemini', count, tables}` — if no real tables exist, `count: 0`
- Cache key: `tables_v3` (old pdfplumber results ignored)

### Streaming — all responses
- Q&A, summary, and key points all use `StreamingResponse` endpoints
- Mobile uses `import { fetch as streamingFetch } from 'expo/fetch'` (WinterCG-compliant, supports `res.body.getReader()`)

---

## Round 2 — Bug fixes

### 1. Streaming not working at the frontend
Three separate causes, all fixed:

**a) Cloudflare buffering** — CF compresses and buffers `text/plain` responses, delivering all chunks at once on the client. Fix: serve all three stream endpoints as `Content-Type: text/event-stream; charset=utf-8` with headers:
```
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
```

**b) Gemini thinking tokens** — Gemini 3 models spend hidden "thinking" tokens that count against `max_output_tokens`, silently truncating answers mid-sentence and adding 10–25 s before the first streamed chunk. Fix: `ThinkingConfig(thinking_budget=0)` on every `GenerateContentConfig`.

**c) Model rate limits / slow TTFB** — `gemini-flash-latest` aliased `gemini-3.5-flash` which hit a 20 req/day free-tier cap. `gemini-3-flash-preview` was heavily rate-limited (~10 s TTFB). Switched to **`gemini-3.1-flash-lite`** (~1.4 s TTFB).

**d) Single-chunk delivery (client-side)** — Even with everything above fixed, `gemini-3.1-flash-lite` generates a full short answer in ~0.15 s, so expo/fetch delivers it as one network chunk → UI renders the complete answer instantly, indistinguishable from non-streaming. Fix: `src/lib/smoothStream.ts` — a pacing layer that sits between the network reader and the UI. Chunks update a `target`, and a ~30 fps `setInterval` reveals progressively longer prefixes at an adaptive rate (`12 %` of remaining backlog per frame). Wired into `chat/[id].tsx` (chat) and `useAnalysisStream` in `hooks.ts` (summary/keypoints).

### 2. Back button showed "(tabs)"
`headerBackButtonDisplayMode: 'minimal'` added to root Stack `screenOptions` in `_layout.tsx`.

### 3. .txt viewer unreadable
WKWebView renders plain text with unstyled pale browser defaults. Fix: detect text-like extensions (`txt text md markdown log csv`) and render them via a native themed `ScrollView` + selectable monospace `Text`. PDFs/images still use WKWebView.

### 4. Theme audit — toggle and all components
- `Switch` fixed: white `thumbColor`, `#C7C7CC` off-track in light mode, `palette.surfacePressed` off-track in dark mode, `palette.accent` on-track
- Full grep audit of `app/` and `components/` — only intentional hardcoded values remain: file-type badge hex colours in `DocumentCard`, modal backdrop `rgba(0,0,0,0.6)` in `UploadMenu`

### 5. Search — exact phrase match only
Rewrote `backend/app/api/routes/search.py`. Old behaviour: BM25 fuzzy ranking returned loosely related docs. New behaviour: case-insensitive literal substring match over each document's `sentences` list. Only documents that literally contain the typed phrase are returned, with the verbatim matching sentence and page number. Fallback: `full_text` scan for phrases that cross sentence boundaries.

---

## Round 3 — Settings / Profile redesign

### Backend additions
- `UserStore.delete(user_id)` — SQL `DELETE` by ID, returns `bool`
- `DELETE /auth/profile` endpoint — deletes account and returns 204

### Mobile auth context
- Added `deleteAccount()` to `AuthValue` interface and `AuthProvider` — calls `DELETE /auth/profile`, clears `AsyncStorage`, resets state

### Settings screen rewrite (`app/(tabs)/settings.tsx`)
Old: flat list of labelled input boxes always visible.

New layout:

**PROFILE card**
- Avatar circle (name initial) + name + "Member since …" subtitle
- Pencil icon → inline name editor with Save / Cancel buttons
- Email row + join date row (separate, with dividers)

**APPEARANCE card** — dark/light toggle (unchanged)

**SERVER card**
- Always shows one status row: green "Connected" + truncated URL + checkmark, or red "Not connected" + URL + chevron
- URL text field + Save button only appear when **not connected** (or if the user taps the connected row to edit)
- Supported formats chips shown only when connected

**ACCOUNT card** (danger-bordered, only when signed in)
- Sign out row
- Delete account row (with "Permanent" label) — double-confirmed alert, deletes server-side then redirects to login

---

## Key files changed

| File | What changed |
|------|-------------|
| `backend/app/services/llm/gemini.py` | `ThinkingConfig(thinking_budget=0)` on all configs; model via `DOCCHAT_GEMINI_MODEL` env var |
| `backend/app/api/routes/documents.py` | `text/event-stream` media type + no-transform headers on all stream routes; Gemini-only tables |
| `backend/app/api/routes/search.py` | Full rewrite to exact substring match |
| `backend/app/api/routes/auth.py` | Added `DELETE /auth/profile` |
| `backend/app/services/storage/user_store.py` | Added `delete()` method |
| `backend/.env` | `DOCCHAT_GEMINI_MODEL=gemini-3.1-flash-lite` |
| `mobile/src/lib/auth.tsx` | Added `deleteAccount()` |
| `mobile/src/lib/smoothStream.ts` | New — adaptive pacing layer for streaming UI |
| `mobile/src/api/client.ts` | `expo/fetch` streaming; `streamText` helper; `askStream`, `summaryStream`, `keypointsStream` |
| `mobile/src/api/hooks.ts` | `useAskStream`, `useAnalysisStream` with smoothStream wired in |
| `mobile/src/app/_layout.tsx` | `headerBackButtonDisplayMode: 'minimal'`; themed nav |
| `mobile/src/app/(tabs)/_layout.tsx` | Tabs layout with Docs / Search / Profile |
| `mobile/src/app/(tabs)/index.tsx` | Pastel document cards + FAB |
| `mobile/src/app/(tabs)/settings.tsx` | Full rewrite — profile info, inline edit, delete account, conditional server URL |
| `mobile/src/app/chat/[id].tsx` | Streaming chat with smooth reveal |
| `mobile/src/app/viewer/[id].tsx` | WKWebView for PDFs; native text render for .txt/.md/etc |
| `mobile/src/components/DocumentCard.tsx` | Pastel tints, badge pills, new layout |
| `mobile/src/components/StatusPill.tsx` | Dot + label pill |
| `mobile/src/lib/analysisParse.ts` | `parseSummaryText`, `parseKeypointsText` for progressive rendering |
| `mobile/src/components/panels/SummaryPanel.tsx` | Streaming panel with inline loading indicator |
| `mobile/src/components/panels/KeyPointsPanel.tsx` | Same |

---

## Model & quota notes

- `gemini-flash-latest` → **avoid** (aliases gemini-3.5-flash, 20 req/day free tier)
- `gemini-3-flash-preview` → **avoid** (~10 s TTFB, heavily rate-limited)
- `gemini-3.1-flash-lite` → **current** (~1.4 s TTFB, stable)
- All configs: `thinking_budget=0` (critical — prevents truncation and latency)
- API key: set in `backend/.env` as `DOCCHAT_GEMINI_API_KEY`

---

## Backend start command
```bash
cd /Users/dev/Desktop/PDF_Chat/backend
.venv/bin/uvicorn "app.api.app:create_app" --factory --host 0.0.0.0 --port 8000
# logs → /tmp/uvicorn.log
```

Cloudflare tunnel: `https://differential-reports-merchant-memorabilia.trycloudflare.com`

---

## npm cache fix (encountered)
```bash
sudo chown -R $(whoami) ~/.npm
```
Run this if `npx expo run:ios --device` fails with `EACCES: permission denied` on the npm cache.
