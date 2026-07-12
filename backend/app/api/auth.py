"""Optional API-key authentication.

When ``DOCCHAT_API_KEYS`` is unset, auth is disabled and every request runs as
the single ``public`` tenant — backward compatible with earlier phases. When
keys are configured, each request must present one (via ``Authorization: Bearer
<key>`` or the ``X-API-Key`` header), and the key becomes the document *owner*,
giving simple multi-tenant isolation without a full user-account system.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

PUBLIC_OWNER = "public"


def _extract_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()
    return None


async def get_owner(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """Resolve the caller's owner identity, enforcing auth when enabled."""

    settings = get_settings()
    if not settings.auth_enabled:
        return PUBLIC_OWNER

    key = _extract_key(authorization, x_api_key)
    if not key or key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return key
