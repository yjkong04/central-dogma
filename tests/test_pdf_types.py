from PIL import Image

from ingest.pdf.types import (
    FigureUnderstander, LayoutDetector, Ocr, Page, PdfIngestError, Region, TextBlock,
)
from ingest.pmc import Figure


def test_types_construct():
    tb = TextBlock(text="hi", bbox=(0, 0, 10, 10), page=0)
    pg = Page(index=0, image=Image.new("RGB", (4, 4)), native_text=[tb])
    rg = Region(kind="figure", bbox=(1, 1, 3, 3), page=0)
    assert pg.native_text[0].text == "hi"
    assert rg.kind == "figure" and rg.score == 1.0
    assert issubclass(PdfIngestError, Exception)


def test_figure_has_optional_local_crop_field():
    fig = Figure(label="Figure 1", caption="a plot", image_bytes=b"\x89PNG")
    assert fig.image_bytes == b"\x89PNG"
    assert Figure(label=None, caption="x").image_bytes is None
