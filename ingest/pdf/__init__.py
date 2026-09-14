"""Self-hosted PDF ingestion: raw PDF -> ParsedPaper (OCR + layout CV)."""
from __future__ import annotations

from .parse import parse_pdf

__all__ = ["parse_pdf"]
