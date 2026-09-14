from pathlib import Path

from PIL import Image

from ingest.chunk import chunk_paper
from ingest.pdf.parse import parse_pdf
from ingest.pdf.types import Region, TextBlock

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
