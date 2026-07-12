"""Domain exceptions.

Using a small typed hierarchy (rather than bare ``ValueError``) lets the future
API layer map failures to HTTP status codes without string-matching messages.
"""

from __future__ import annotations


class DocChatError(Exception):
    """Base class for all application-specific errors."""


class UnsupportedFormatError(DocChatError):
    """Raised when no extractor can handle a given file/MIME type."""


class ExtractionError(DocChatError):
    """Raised when a file matched an extractor but could not be parsed."""


class EmptyDocumentError(DocChatError):
    """Raised when extraction yields no usable text."""


class IndexNotBuiltError(DocChatError):
    """Raised when a query is issued before the retrieval index exists."""
