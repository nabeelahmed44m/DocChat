"""Document ownership resolution.

Priority order for ``get_owner``:
1. Valid JWT (user account) → returns the user's UUID (``sub`` claim).
   This is what the mobile app sends after login via ``/auth/login``.
2. API key (``Authorization: Bearer <key>`` or ``X-API-Key`` header) →
   returns the key string; only checked when ``DOCCHAT_API_KEYS`` is set.
3. No credentials / auth disabled → returns ``"public"`` (single tenant).

The JWT check is always attempted first so logged-in users always get their
own scoped bucket, even when ``DOCCHAT_API_KEYS`` is empty.
"""

from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

PUBLIC_OWNER = "public"


def _bearer_token(authorization: str | None) -> str | None:
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return None


async def get_owner(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> str:
    """Resolve the caller's owner identity."""

    # 1. Try JWT — always, regardless of whether API-key auth is enabled.
    token = _bearer_token(authorization)
    if token:
        try:
            payload = pyjwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            user_id: str | None = payload.get("sub")
            if user_id:
                return user_id
        except pyjwt.InvalidTokenError:
            pass  # not a valid JWT; fall through to API-key check

    # 2. API-key auth (opt-in via DOCCHAT_API_KEYS).
    if settings.auth_enabled:
        key = (x_api_key or "").strip() or token or ""
        if not key or key not in settings.api_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing or invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return key

    return PUBLIC_OWNER
