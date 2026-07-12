"""Health and capability endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.services.extraction import supported_extensions
from app.services.extraction.libreoffice import soffice_binary
from app.services.extraction.ocr import ocr_available

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, object]:
    """Liveness probe plus a snapshot of what the server can currently do."""

    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "supported_extensions": list(supported_extensions()),
        "ocr_available": ocr_available(),
        "libreoffice_available": soffice_binary() is not None,
        "lsa_enabled": settings.lsa_enabled,
        "auth_required": settings.auth_enabled,
        "store_backend": settings.store_backend,
        "multi_document_search": True,
    }
