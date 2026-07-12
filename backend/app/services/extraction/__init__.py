"""Format extractors and the dispatcher that selects one per file."""

from app.services.extraction.dispatcher import extract, supported_extensions

__all__ = ["extract", "supported_extensions"]
