"""Application configuration.

Settings are read from environment variables (optionally a local ``.env`` file)
so the same code runs unchanged across dev, CI, and production. Nothing here is
secret by default, but keeping it centralized means we never sprinkle magic
numbers through the pipeline.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Doc Chat backend."""

    model_config = SettingsConfigDict(
        env_prefix="DOCCHAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Environment -------------------------------------------------------
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # --- Passage construction ---------------------------------------------
    # A passage is a sliding window of sentences used as the retrieval unit.
    passage_window: int = Field(default=4, ge=1, description="Sentences per passage")
    passage_stride: int = Field(default=2, ge=1, description="Sentence step between passages")

    # --- Retrieval / ranking ----------------------------------------------
    top_k_passages: int = Field(default=5, ge=1, description="Passages retrieved by BM25")
    top_k_answers: int = Field(default=3, ge=1, description="Answer sentences returned")
    context_sentences: int = Field(
        default=1, ge=0, description="Neighboring sentences included around an answer"
    )
    # Weight blending sparse (BM25), TF-IDF cosine, and LSA (latent-semantic)
    # sentence scores. The three need not sum to 1; they're relative weights.
    bm25_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    tfidf_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    lsa_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    min_answer_score: float = Field(
        default=0.0, description="Answers scoring below this are dropped"
    )

    # --- Dense retrieval (LSA) --------------------------------------------
    # LSA (TruncatedSVD over TF-IDF) adds synonymy-aware matching without any
    # neural model — still fully classical NLP, no LLM, works offline.
    lsa_enabled: bool = Field(default=True, description="Enable LSA dense retrieval")
    lsa_components: int = Field(
        default=128, ge=2, description="Latent dimensions for TruncatedSVD"
    )

    # --- Ingestion limits --------------------------------------------------
    max_file_bytes: int = Field(default=50 * 1024 * 1024, description="Upload size ceiling")

    # --- API --------------------------------------------------------------
    api_title: str = Field(default="Gist API")
    api_version: str = Field(default="0.5.0")
    cors_origins: list[str] = Field(
        default=["*"], description="Allowed CORS origins for the mobile/web client"
    )

    # --- Auth (optional, opt-in) ------------------------------------------
    # When empty, auth is disabled (open access, single "public" tenant). When
    # set, requests must present a matching key and documents are scoped per key.
    api_keys: list[str] = Field(
        default_factory=list, description="Valid API keys; empty disables auth"
    )
    # JWT secret for user auth — change this in production.
    jwt_secret: str = Field(
        default="change-me-in-production-please",
        description="Secret key used to sign JWT tokens",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_hours: int = Field(default=720, description="Token validity in hours (30 days)")

    # --- Storage ----------------------------------------------------------
    store_backend: str = Field(
        default="json", description="Document store backend: 'json' or 'sql'"
    )
    database_url: str = Field(
        default="",
        description="SQLAlchemy URL for the 'sql' backend (defaults to SQLite under storage_dir)",
    )
    storage_dir: Path = Field(
        default=Path("./data"),
        description="Where uploaded files and document metadata are persisted",
    )
    ingest_workers: int = Field(
        default=2, ge=1, description="Thread-pool size for background ingestion"
    )
    engine_cache_size: int = Field(
        default=32,
        ge=1,
        description="Max in-memory QA engines kept (LRU); evicted ones are rebuilt on demand",
    )

    # --- Stripe billing (optional) ----------------------------------------
    # Leave blank to disable billing enforcement. When set, uploads above
    # free_tier_bytes require an active Pro subscription.
    stripe_secret_key: str = Field(default="", description="Stripe secret key (sk_live_… or sk_test_…)")
    stripe_webhook_secret: str = Field(default="", description="Stripe webhook signing secret (whsec_…)")
    stripe_price_id: str = Field(default="", description="Stripe Price ID for the Pro plan (price_…)")
    # Public URL of this server — used to build Stripe success/cancel redirect URLs.
    server_base_url: str = Field(
        default="http://localhost:8000",
        description="Public HTTPS URL of this server (e.g. your Cloudflare tunnel URL)",
    )
    free_tier_bytes: int = Field(
        default=1 * 1024 * 1024,
        description="Max upload size on the free plan (default 1 MB)",
    )

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_id)

    # --- Cloudflare R2 object storage (optional) --------------------------
    # Leave blank to keep files on local disk. When all four are set, uploaded
    # files are written to R2 for durability; the local copy is kept as a hot
    # cache for the ingestion thread and FileResponse serving.
    r2_account_id: str = Field(default="", description="Cloudflare account ID")
    r2_access_key_id: str = Field(default="", description="R2 API token access key ID")
    r2_secret_access_key: str = Field(default="", description="R2 API token secret")
    r2_bucket_name: str = Field(default="", description="R2 bucket name")

    @property
    def r2_enabled(self) -> bool:
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

    # --- Gemini LLM -------------------------------------------------------
    gemini_api_key: str = Field(default="", description="Google AI Studio API key")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model ID")

    # --- OCR --------------------------------------------------------------
    ocr_enabled: bool = Field(
        default=True, description="Attempt OCR for images and text-less PDFs"
    )
    ocr_language: str = Field(default="eng", description="Tesseract language code(s)")

    # --- LibreOffice fallback for legacy formats --------------------------
    libreoffice_enabled: bool = Field(
        default=True, description="Use `soffice` to convert legacy .doc/.rtf/.odt"
    )

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def registry_path(self) -> Path:
        return self.storage_dir / "registry.json"

    @property
    def auth_enabled(self) -> bool:
        return len(self.api_keys) > 0

    @property
    def resolved_database_url(self) -> str:
        """The SQLAlchemy URL for the SQL backend.

        Normalizes Postgres URLs (e.g. from Neon, which hands out
        ``postgres://`` / ``postgresql://``) to the psycopg3 driver so no
        separate driver-name juggling is needed in deployment.
        """

        url = self.database_url
        if not url:
            return f"sqlite:///{(self.storage_dir / 'docchat.db').as_posix()}"
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance."""

    return Settings()
