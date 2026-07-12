"""ASGI entry point.

Run with::

    uvicorn app.main:app --reload            # development
    uvicorn app.main:app --host 0.0.0.0 --port 8000   # production-ish

``app`` is a module-level instance so process managers (uvicorn/gunicorn) can
import it directly.
"""

from __future__ import annotations

from app.api import create_app

app = create_app()


def run() -> None:
    """Convenience launcher: ``python -m app.main``."""

    import uvicorn

    from app.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    run()
