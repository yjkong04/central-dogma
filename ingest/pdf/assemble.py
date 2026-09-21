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


def _text_of(region: Region, blocks: list[TextBlock]) -> str:
    return " ".join(b.text for b in _blocks_in(region, blocks)).strip()


def _vertical_gap(a: Region, b: Region) -> float:
    """Vertical gap between two regions; 0 if they overlap vertically."""
    ay0, ay1 = a.bbox[1], a.bbox[3]
    by0, by1 = b.bbox[1], b.bbox[3]
    if by0 >= ay1:
        return by0 - ay1
    if by1 <= ay0:
        return ay0 - by1
    return 0.0


def _nearest_caption(region: Region, regions: list[Region], claimed: set[int],
                      threshold: float) -> Region | None:
    """The unclaimed caption region with the smallest vertical gap to `region`.

    Considers captions both above and below (table captions are often above),
    and excludes captions already claimed by an earlier figure/table on the
    same page so one caption is never attached to two figures.
    """
    best: Region | None = None
    best_gap = None
    for r in regions:
        if r.kind != "caption" or id(r) in claimed:
            continue
        gap = _vertical_gap(region, r)
        if gap > threshold:
            continue
        if best_gap is None or gap < best_gap:
            best, best_gap = r, gap
    return best


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
        claimed_captions: set[int] = set()
        for region in regions:
            if region.kind in ("figure", "table"):
                crop = _crop_png(page.image, region)
                threshold = page.image.height * 0.15
                cap_region = _nearest_caption(region, regions, claimed_captions, threshold)
                raw_caption = ""
                if cap_region is not None:
                    raw_caption = _text_of(cap_region, blocks)
                    claimed_captions.add(id(cap_region))
                label = _label_from(raw_caption)
                caption = understander.describe(
                    Image.open(io.BytesIO(crop)), raw_caption) or raw_caption or "figure"
                figures.append(Figure(
                    label=label, caption=caption, image_bytes=crop))
            elif region.kind == "title":
                heading = _text_of(region, blocks)
                current = Section(title=heading or None, text="")
                sections.append(current)
            elif region.kind in ("text", "list"):
                body = _text_of(region, blocks)
                if not body:
                    continue
                if current is None:
                    current = Section(title=None, text="")
                    sections.append(current)
                current.text = (current.text + " " + body).strip() if current.text else body

    sections = [s for s in sections if s.text or s.title]
    return ParsedPaper(paper_id=paper_id, title=title, sections=sections, figures=figures)
