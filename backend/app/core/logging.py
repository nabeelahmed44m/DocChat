"""Central logging setup.

A single ``configure_logging`` entry point keeps formatting consistent between
the CLI and the future FastAPI process. Idempotent so tests can call it freely.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Initialize root logging once, honoring ``DOCCHAT_LOG_LEVEL``."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = (level or get_settings().log_level).upper()
    logging.basicConfig(
        level=resolved,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for ``name``."""

    configure_logging()
    return logging.getLogger(name)
