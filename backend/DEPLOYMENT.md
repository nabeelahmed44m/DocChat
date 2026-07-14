# Deploying the Gist backend to the cloud

## Why not Vercel (read first)

Vercel only runs Python as **serverless functions**, and this backend is built
around things serverless cannot do:

- **No system binaries** — OCR needs the `tesseract` binary; Vercel functions
  can't install apt packages, so every scanned PDF/image upload would fail.
- **250 MB bundle limit** — `scikit-learn` + `numpy` + `pymupdf` + `pdfplumber`
  + `boto3` + `stripe` together sit right at or over the unzipped limit.
- **Background ingestion dies** — uploads return `202` and are processed by a
  thread pool (`DOCCHAT_INGEST_WORKERS`). Serverless kills the process as soon
  as the response is sent, so documents would stay stuck in `processing`.
- **Engine cache is useless across cold starts** — every question would rebuild
  the BM25/TF-IDF/LSA indexes from scratch.

The repo already ships a production `backend/Dockerfile` (installs tesseract,
runs uvicorn). Deploy that container to any Docker host instead. Good options,
easiest first: **Railway**, **Render**, **Fly.io**, **Google Cloud Run**.
State is already externalized (Neon Postgres + Cloudflare R2), so a single
stateless container is all you need.

## Option A — Railway (recommended)

1. Push the repo to GitHub.
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Settings → set **Root Directory** to `backend` (it auto-detects the Dockerfile).
4. Variables → paste the production env vars (see below).
5. Settings → Networking → Generate Domain. That URL is your backend URL.

Deploys rebuild automatically on every push to `main`.

## Option B — Render

1. [render.com](https://render.com) → New → Web Service → connect the repo.
2. Root Directory: `backend`, Runtime: **Docker**.
3. Add the env vars, deploy, copy the `https://….onrender.com` URL.
   (Free tier spins down when idle — first request after idle takes ~1 min.)

## Option C — Fly.io / Cloud Run

```bash
# Fly
cd backend && fly launch --no-deploy   # detects Dockerfile
fly secrets set DOCCHAT_DATABASE_URL=… DOCCHAT_JWT_SECRET=… # etc.
fly deploy

# Cloud Run
gcloud run deploy gist-api --source backend --region us-east1 \
  --allow-unauthenticated --set-env-vars "DOCCHAT_STORE_BACKEND=sql,…"
```

## Production environment variables

Copy the values from your local `backend/.env` (never commit it). The ones that
matter in production:

```bash
DOCCHAT_ENVIRONMENT=production
DOCCHAT_LOG_LEVEL=INFO

# State (already externalized)
DOCCHAT_STORE_BACKEND=sql
DOCCHAT_DATABASE_URL=postgresql://…neon.tech/…?sslmode=require   # Neon
DOCCHAT_R2_ACCOUNT_ID=…
DOCCHAT_R2_ACCESS_KEY_ID=…
DOCCHAT_R2_SECRET_ACCESS_KEY=…
DOCCHAT_R2_BUCKET_NAME=pdf-chat-docs

# Auth — generate a fresh secret: python -c "import secrets; print(secrets.token_urlsafe(48))"
DOCCHAT_JWT_SECRET=<new-random-value, not the dev one>

# Billing
DOCCHAT_STRIPE_SECRET_KEY=sk_live_…        # or sk_test_ while testing
DOCCHAT_STRIPE_PRICE_ID=price_…
DOCCHAT_STRIPE_WEBHOOK_SECRET=whsec_…      # from the webhook endpoint below
DOCCHAT_SERVER_BASE_URL=https://<your-deployed-url>   # used in Stripe redirect URLs

# LLM
DOCCHAT_GEMINI_API_KEY=…
DOCCHAT_GEMINI_MODEL=gemini-3-flash-preview

# Lock CORS down (mobile apps don't send Origin, so this only affects web)
DOCCHAT_CORS_ORIGINS=["https://your-web-origin"]      # or ["*"] if mobile-only

DOCCHAT_OCR_ENABLED=true
DOCCHAT_LIBREOFFICE_ENABLED=false   # soffice isn't in the image
```

## After the backend is live

1. **Stripe webhook**: Stripe dashboard → Developers → Webhooks → Add endpoint
   `https://<deployed-url>/billing/webhook`, subscribe to the subscription
   events, copy the signing secret into `DOCCHAT_STRIPE_WEBHOOK_SECRET`, redeploy.
2. **Smoke test**: `curl https://<deployed-url>/health` — expect
   `"store_backend":"sql"`, `"ocr_available":true`.
3. **Point the app at it**: set `EXPO_PUBLIC_API_URL=https://<deployed-url>` in
   `mobile/.env`, then rebuild (`npx expo start` for dev, `eas build` for store
   builds — the URL is inlined at build time, so production builds need it set
   at build time, e.g. via `eas.json` env or EAS secrets).
