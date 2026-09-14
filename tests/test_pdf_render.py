from pathlib import Path

import pytest

from ingest.pdf.render import render_pdf
from ingest.pdf.types import PdfIngestError

FIXTURE = Path("tests/fixtures/pdf/born_digital.pdf")


def test_render_returns_pages_with_image_and_native_text():
    pages = render_pdf(FIXTURE)
    assert len(pages) == 1
    pg = pages[0]
    assert pg.index == 0
    assert pg.image.width > 0 and pg.image.height > 0
    # born-digital fixture has a real text layer
    joined = " ".join(b.text for b in pg.native_text)
    assert "Introduction" in joined


def test_render_missing_file_raises_typed_error():
    with pytest.raises(PdfIngestError):
        render_pdf(Path("tests/fixtures/pdf/does_not_exist.pdf"))
