"""Fuse per-page text blocks + layout regions into a ParsedPaper.

Pure: no I/O, no models. Cropping uses the in-memory page image. Regions are
processed top-to-bottom per page (reading order for single-column papers;
multi-column refinement is a future enhancement, not needed for retrieval).
"""
from __future__ import annotations

import io
import re

from PIL import Image

from ingest.pmc import Figure, ParsedPaper, Section

from .types import FigureUnderstander, Page, Region, TextBlock

_LABEL_RE = re.compile(r"(figure|fig|table)\s*\.?\s*(\d+)", re.IGNORECASE)


def _blocks_in(region: Region, blocks: list[TextBlock]) -> list[TextBlock]:
    rx0, ry0, rx1, ry1 = region.bbox
    out = []
    for b in blocks:
        bx0, by0, bx1, by1 = b.bbox
        cy = (by0 + by1) / 2
        cx = (bx0 + bx1) / 2
        if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
            out.append(b)
    return out


def _crop_png(image: Image.Image, bbox: Region) -> bytes:
    x0, y0, x1, y1 = (int(v) for v in bbox.bbox)
    x0, y0 = max(0, x0), max(0, y0)
    crop = image.crop((x0, y0, min(x1, image.width), min(y1, image.height)))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return buf.getvalue()


def _label_from(caption: str) -> str | None:
    m = _LABEL_RE.search(caption or "")
    if not m:
        return None
    kind = "Table" if m.group(1).lower() == "table" else "Figure"
    return f"{kind} {m.group(2)}"


def assemble(paper_id: str, title: str | None, pages: list[Page],
             text_by_page: dict[int, list[TextBlock]],
             regions_by_page: dict[int, list[Region]],
             understander: FigureUnderstander) -> ParsedPaper:
    sections: list[Section] = []
    figures: list[Figure] = []
    current: Section | None = None

    for page in sorted(pages, key=lambda p: p.index):
        regions = sorted(regions_by_page.get(page.index, []), key=lambda r: r.bbox[1])
        blocks = text_by_page.get(page.index, [])
        for region in regions:
            if region.kind in ("figure", "table"):
                crop = _crop_png(page.image, region)
                cap_regions = [r for r in regions if r.kind == "caption"
                               and abs(r.bbox[1] - region.bbox[3]) < page.image.height * 0.15]
                caption = ""
                if cap_regions:
                    caption = " ".join(b.text for b in _blocks_in(cap_regions[0], blocks)).strip()
                caption = understander.describe(
                    Image.open(io.BytesIO(crop)), caption) or caption or "figure"
                figures.append(Figure(
                    label=_label_from(caption), caption=caption, image_bytes=crop))
            elif region.kind == "title":
                heading = " ".join(b.text for b in _blocks_in(region, blocks)).strip()
                current = Section(title=heading or None, text="")
                sections.append(current)
            elif region.kind in ("text", "list"):
                body = " ".join(b.text for b in _blocks_in(region, blocks)).strip()
                if not body:
                    continue
                if current is None:
                    current = Section(title=None, text="")
                    sections.append(current)
                current.text = (current.text + " " + body).strip() if current.text else body

    sections = [s for s in sections if s.text or s.title]
    return ParsedPaper(paper_id=paper_id, title=title, sections=sections, figures=figures)
