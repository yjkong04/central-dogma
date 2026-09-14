"""Rasterize PDF pages and extract the native text layer (if any).

pypdfium2 is a lightweight, CPU-only binding fast enough to run in CI, so
rendering is not gated behind the slow marker.
"""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from .types import Page, PdfIngestError, TextBlock


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
            page = doc[i]
            image: Image.Image = page.render(scale=scale).to_pil().convert("RGB")
            native = _native_text(page, scale, i)
            pages.append(Page(index=i, image=image, native_text=native))
    finally:
        doc.close()
    return pages


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
    except Exception:
        return []
    finally:
        tp.close()
    return blocks
