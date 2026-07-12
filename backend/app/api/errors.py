"""Map domain exceptions to HTTP responses.

Registering handlers here (rather than try/except in each route) keeps routes
thin and guarantees every failure returns the same ``ErrorResponse`` shape with
a machine-readable ``code`` the mobile client can branch on.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from google.genai.errors import ClientError as GeminiClientError

from app.core.exceptions import (
    DocChatError,
    EmptyDocumentError,
    ExtractionError,
    UnsupportedFormatError,
)

# Domain error -> (HTTP status, stable error code).
_ERROR_MAP: dict[type[DocChatError], tuple[int, str]] = {
    UnsupportedFormatError: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_format"),
    EmptyDocumentError: (status.HTTP_422_UNPROCESSABLE_ENTITY, "empty_document"),
    ExtractionError: (status.HTTP_422_UNPROCESSABLE_ENTITY, "extraction_failed"),
}


def _payload(detail: str, code: str) -> dict[str, str]:
    return {"detail": detail, "code": code}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DocChatError)
    async def _handle_docchat_error(_: Request, exc: DocChatError):
        http_status, code = _ERROR_MAP.get(
            type(exc), (status.HTTP_400_BAD_REQUEST, "bad_request")
        )
        return JSONResponse(status_code=http_status, content=_payload(str(exc), code))

    @app.exception_handler(FileNotFoundError)
    async def _handle_missing_file(_: Request, exc: FileNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_payload(str(exc), "not_found"),
        )

    @app.exception_handler(GeminiClientError)
    async def _handle_gemini_error(_: Request, exc: GeminiClientError):
        exc_status = getattr(exc, "status", None) or getattr(exc, "code", 0)
        if exc_status == 429 or "RESOURCE_EXHAUSTED" in str(exc):
            detail = "Gemini quota exhausted — please check your API key or try again later."
            code = "gemini_quota_exceeded"
            http = status.HTTP_503_SERVICE_UNAVAILABLE
        elif exc_status == 400:
            detail = f"Gemini request invalid: {exc.message}"
            code = "gemini_bad_request"
            http = status.HTTP_400_BAD_REQUEST
        else:
            detail = f"Gemini API error: {exc.message}"
            code = "gemini_error"
            http = status.HTTP_502_BAD_GATEWAY
        return JSONResponse(status_code=http, content=_payload(detail, code))

    @app.exception_handler(ValueError)
    async def _handle_value_error(_: Request, exc: ValueError):
        # Catches "DOCCHAT_GEMINI_API_KEY is not set"
        if "GEMINI_API_KEY" in str(exc):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=_payload(str(exc), "gemini_key_missing"),
            )
        raise exc
