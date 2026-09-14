from PIL import Image

from ingest.pdf.ocr import needs_ocr, text_for_page
from ingest.pdf.types import Page, TextBlock


def _page(texts: list[str]) -> Page:
    blocks = [TextBlock(text=t, bbox=(0, 0, 1, 1), page=0) for t in texts]
    return Page(index=0, image=Image.new("RGB", (8, 8)), native_text=blocks)


class FakeOcr:
    def run(self, image, page):
        return [TextBlock(text="ocr text here", bbox=(0, 0, 1, 1), page=page)]


def test_needs_ocr_true_when_text_layer_is_sparse():
    assert needs_ocr(_page([])) is True
    assert needs_ocr(_page(["hi"])) is True  # < 20 chars


def test_needs_ocr_false_when_text_layer_is_rich():
    assert needs_ocr(_page(["this page already has plenty of embedded text"])) is False


def test_text_for_page_uses_native_when_present():
    page = _page(["this page already has plenty of embedded text"])
    out = text_for_page(page, FakeOcr())
    assert out == page.native_text  # native kept, OCR not invoked


def test_text_for_page_falls_back_to_ocr_when_sparse():
    out = text_for_page(_page([]), FakeOcr())
    assert len(out) == 1 and out[0].text == "ocr text here"
