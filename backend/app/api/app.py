"""FastAPI application factory.

``create_app`` wires configuration, the document store, the ingestion service,
CORS, error handlers, and routers. Using a factory (not a module-level global)
lets tests spin up isolated apps with their own temp storage.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_error_handlers
from app.api.routes import auth, documents, health, search
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.services.ingestion import IngestionService
from app.services.storage import create_store

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = create_store(settings)
        app.state.ingestion = IngestionService(app.state.store, settings)
        logger.info(
            "Doc Chat API %s started (store=%s, auth=%s)",
            __version__,
            settings.store_backend,
            "on" if settings.auth_enabled else "off",
        )
        try:
            yield
        finally:
            app.state.ingestion.shutdown()
            logger.info("Doc Chat API shutting down")

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Classical-NLP document question answering (no LLMs).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # A wildcard origin and credentials are mutually exclusive per the CORS
        # spec; auth here is header-based (bearer), not cookie-based, so we only
        # enable credentials when explicit origins are configured.
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    return app
