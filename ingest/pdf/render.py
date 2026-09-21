"""Rasterize PDF pages and extract the native text layer (if any).

pypdfium2 is a lightweight, CPU-only binding fast enough to run in CI, so
rendering is not gated behind the slow marker.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from .types import Page, PdfIngestError, TextBlock

logger = logging.getLogger(__name__)

# Untrusted PDFs can declare huge page dimensions; without a cap a single
# page can try to allocate an enormous bitmap (OOM / DoS). ~40 MP is well
# above any normal document page at typical ingestion DPI.
MAX_RENDER_PX = 40_000_000  # ~40 MP cap per rendered page


class RenderError(PdfIngestError):
    """Base class for page-render failures."""


class RenderTooLarge(RenderError):
    """Raised when a page's rendered bitmap would exceed MAX_RENDER_PX."""


def render_pdf(path: str | Path, dpi: int = 200, max_pages: int = 40) -> list[Page]:
    p = Path(path)
    if not p.exists():
        raise PdfIngestError(f"PDF not found: {p}")
    scale = dpi / 72.0
    try:
        doc = pdfium.PdfDocument(str(p))
    except Exception as e:  # pypdfium raises assorted errors on bad input
        raise PdfIngestError(f"cannot open PDF {p}: {e}") from e
    pages: list[Page] = []
    try:
        for i in range(min(len(doc), max_pages)):
            try:
                page = doc[i]
                image = _rasterize_page(page, i, dpi)
            except Exception as e:  # untrusted page: isolate, don't abort the whole PDF
                logger.warning("skipping page %d of %s: %s", i, p, e)
                continue
            try:
                native = _native_text(page, scale, i)
            except Exception as e:  # text extraction bug: keep the rendered image, drop text
                logger.warning(
                    "native text extraction failed for page %d of %s: %s", i, p, e
                )
                native = []
            pages.append(Page(index=i, image=image, native_text=native))
    finally:
        doc.close()
    return pages


def _guard_render_size(width_px: int, height_px: int) -> None:
    """Raise RenderTooLarge if the requested bitmap would exceed MAX_RENDER_PX."""
    if width_px * height_px > MAX_RENDER_PX:
        raise RenderTooLarge(
            f"render size {width_px}x{height_px} exceeds cap {MAX_RENDER_PX}"
        )


def _rasterize_page(page: "pdfium.PdfPage", index: int, dpi: int) -> Image.Image:
    """Render a single page to a PIL image, bounded by MAX_RENDER_PX."""
    scale = dpi / 72.0
    width_pt, height_pt = page.get_size()
    _guard_render_size(int(width_pt * scale), int(height_pt * scale))
    return page.render(scale=scale).to_pil().convert("RGB")


def _native_text(page: "pdfium.PdfPage", scale: float, page_index: int) -> list[TextBlock]:
    """Word-ish text blocks from the embedded text layer; [] if none."""
    tp = page.get_textpage()
    blocks: list[TextBlock] = []
    try:
        n = tp.count_rects()
        for r in range(n):
            # get_rect returns (left, bottom, right, top) in PDF points
            x0, y0, x1, y1 = tp.get_rect(r)
            text = tp.get_text_bounded(x0, y0, x1, y1).strip()
            if not text:
                continue
            ph = page.get_height()
            # to top-left pixel space
            bbox = (x0 * scale, (ph - y1) * scale, x1 * scale, (ph - y0) * scale)
            blocks.append(TextBlock(text=text, bbox=bbox, page=page_index))
    except pdfium.PdfiumError:
        # No usable text layer on this page: fall back to OCR upstream.
        return []
    finally:
        tp.close()
    return blocks
