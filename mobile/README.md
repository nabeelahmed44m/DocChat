# Doc Chat — Mobile App (Phase 3)

React Native + Expo client for the Doc Chat backend. Upload any document (or scan
a paper page with the camera), then ask questions and get answers that are exact
quotes with page citations — no LLM, no hallucination.

## Stack

- **Expo SDK 57** + **Expo Router** (file-based navigation, typed routes)
- **React Query** for data fetching, caching, and status polling
- **expo-document-picker / expo-image-picker** for file, photo, and camera-scan uploads
- **FlashList** for the chat transcript, **lucide-react-native** icons
- Custom dark-first design system (`src/theme/theme.ts`) — no UI framework lock-in

## Project structure

```
src/
├── app/                 Expo Router screens
│   ├── _layout.tsx        providers (Query, Settings, theme) + Stack
│   ├── index.tsx          documents list + upload flow
│   ├── chat/[id].tsx      chat screen (processing → ready → Q&A)
│   └── settings.tsx       backend URL + connection status
├── api/                 client.ts (typed HTTP) · hooks.ts (React Query) · types.ts
├── components/          DocumentCard, AnswerCard, ChatComposer, UploadMenu, StatusPill…
│   └── ui/              Text, Button, Card primitives
├── lib/                 settings (persisted base URL) · pick (file/photo/camera) · format
└── theme/               design tokens
```

## Running it

```bash
npm install
npx expo start          # then press i (iOS), a (Android), or scan the QR in Expo Go
```

### Connecting to the backend

The app needs to reach the FastAPI backend (see `../backend`). Set the address in
the app's **Settings** screen:

- **iOS simulator:** `http://127.0.0.1:8000` (the default)
- **Android emulator:** `http://10.0.2.2:8000` (the default)
- **Physical device:** your computer's LAN IP, e.g. `http://192.168.1.20:8000`
  (run the backend with `uvicorn app.main:app --host 0.0.0.0 --port 8000`)

Settings shows live connection status, the API version, and OCR availability.

## How it works

1. **Upload** — pick a file, choose a photo, or scan with the camera. The file is
   POSTed to `/documents`; the server returns a `queued` record.
2. **Processing** — the chat screen polls `/documents/{id}/status` (React Query)
   and shows a live `queued → processing → ready` state.
3. **Ask** — once `ready`, questions go to `/documents/{id}/ask`. Each answer
   renders as a card with the verbatim quote, a page-citation chip, a relevance
   bar, matched entities (dates/amounts), and expandable context.

## Type-safety & validation

```bash
npx tsc --noEmit                 # typecheck
npx expo-doctor                  # dependency/config checks
npx expo export --platform ios   # full Metro bundle (compile-time validation)
```

All three pass in CI-equivalent local runs.
