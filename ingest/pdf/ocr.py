"""OCR fallback for pages whose native text layer is missing/sparse.

Pure decision + selection logic is tested with a fake Ocr; the real docTR
adapter is exercised only by slow-marked integration tests.
"""
from __future__ import annotations

from PIL import Image

from .types import Ocr, Page, TextBlock


def needs_ocr(page: Page, min_chars: int = 20) -> bool:
    chars = sum(len(b.text) for b in page.native_text)
    return chars < min_chars


def text_for_page(page: Page, ocr: Ocr, min_chars: int = 20) -> list[TextBlock]:
    if needs_ocr(page, min_chars):
        return ocr.run(page.image, page.index)
    return page.native_text


class DoctrOcr:
    """Real CPU OCR via docTR. Lazy-imported so the dep is optional."""

    def __init__(self) -> None:
        from doctr.models import ocr_predictor  # type: ignore

        self._model = ocr_predictor(pretrained=True)

    def run(self, image: Image.Image, page: int) -> list[TextBlock]:
        import numpy as np

        arr = np.array(image.convert("RGB"))
        result = self._model([arr])
        w, h = image.size
        blocks: list[TextBlock] = []
        for pg in result.pages:
            for block in pg.blocks:
                for line in block.lines:
                    text = " ".join(word.value for word in line.words).strip()
                    if not text:
                        continue
                    (x0, y0), (x1, y1) = line.geometry  # relative 0..1
                    blocks.append(TextBlock(
                        text=text, bbox=(x0 * w, y0 * h, x1 * w, y1 * h), page=page))
        return blocks
