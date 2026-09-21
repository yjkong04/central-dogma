"""Orchestrate: PDF -> render -> (native|OCR) text -> layout -> assemble."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ingest.pmc import ParsedPaper

from .assemble import assemble
from .caption import CaptionTextUnderstander
from .ocr import text_for_page
from .render import render_pdf
from .types import FigureUnderstander, LayoutDetector, Ocr, PdfIngestError


def _paper_id(path: Path) -> str:
    return "pdf-" + hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def parse_pdf(path, *, ocr: Ocr | None = None, layout: LayoutDetector | None = None,
              understander: FigureUnderstander | None = None,
              dpi: int = 200, max_pages: int = 40) -> ParsedPaper:
    p = Path(path)
    if layout is None:  # pragma: no cover - requires a model checkpoint
        raise ValueError("a LayoutDetector is required (no default checkpoint bundled)")
    if ocr is None:
        from .ocr import DoctrOcr
        ocr = DoctrOcr()
    understander = understander or CaptionTextUnderstander()

    pages = render_pdf(p, dpi=dpi, max_pages=max_pages)
    text_by_page = {pg.index: _ocr_page(pg, ocr) for pg in pages}
    regions_by_page = {pg.index: _detect_layout(pg, layout) for pg in pages}
    title = _guess_title(text_by_page)
    return assemble(_paper_id(p), title, pages, text_by_page, regions_by_page, understander)


def _ocr_page(page, ocr: Ocr):
    try:
        return text_for_page(page, ocr)
    except PdfIngestError:
        raise
    except Exception as e:  # OCR backends raise assorted errors on bad pages
        raise PdfIngestError(f"OCR failed on page {page.index}: {e}") from e


def _detect_layout(page, layout: LayoutDetector):
    try:
        return layout.detect(page.image, page.index)
    except PdfIngestError:
        raise
    except Exception as e:  # layout backends raise assorted errors on bad pages
        raise PdfIngestError(f"layout detection failed on page {page.index}: {e}") from e


def _guess_title(text_by_page) -> str | None:
    first = text_by_page.get(0) or []
    return first[0].text.strip() if first else None
