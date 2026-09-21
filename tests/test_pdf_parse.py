from pathlib import Path

import pytest

from ingest.chunk import chunk_paper
from ingest.pdf.parse import parse_pdf
from ingest.pdf.types import PdfIngestError, Region, TextBlock

FIXTURE = Path("tests/fixtures/pdf/born_digital.pdf")


class FakeLayout:
    """One title + one text region covering the page (born-digital has text)."""
    def detect(self, image, page):
        w, h = image.size
        return [Region("title", (0, 0, w, h * 0.15), page),
                Region("text", (0, h * 0.15, w, h), page)]


class FakeOcr:
    def run(self, image, page):
        return [TextBlock(text="unused", bbox=(0, 0, 1, 1), page=page)]


def test_parse_pdf_produces_parsedpaper_and_chunks():
    paper = parse_pdf(FIXTURE, ocr=FakeOcr(), layout=FakeLayout())
    assert paper.paper_id.startswith("pdf-")
    assert paper.sections, "expected at least one section"
    joined = " ".join(s.text for s in paper.sections)
    assert "born-digital" in joined.lower()

    chunks = chunk_paper(paper)
    assert any(c.modality == "text" for c in chunks)
    assert all(c.paper_id == paper.paper_id for c in chunks)


def test_ocr_backend_failure_raises_typed_pdf_ingest_error():
    from ingest.pdf.parse import _ocr_page
    from ingest.pdf.types import Page

    class BrokenOcr:
        def run(self, image, page):
            raise RuntimeError("OCR backend crashed")

    scanned_page = Page(index=0, image=None, native_text=[])  # sparse -> triggers OCR
    with pytest.raises(PdfIngestError):
        _ocr_page(scanned_page, BrokenOcr())


def test_layout_backend_failure_raises_typed_pdf_ingest_error():
    from ingest.pdf.parse import _detect_layout
    from ingest.pdf.types import Page

    class BrokenLayout:
        def detect(self, image, page):
            raise RuntimeError("layout model crashed")

    page = Page(index=0, image=None, native_text=[])
    with pytest.raises(PdfIngestError):
        _detect_layout(page, BrokenLayout())
