"""Document-layout detection via a YOLO/DETR model trained on DocLayNet/PubLayNet.

The label→kind mapping is pure and unit-tested; the model call itself is only
run by slow-marked integration tests.
"""
from __future__ import annotations

from PIL import Image

from .types import Region

# DocLayNet / PubLayNet style class names -> our canonical kinds.
_LABEL_MAP = {
    "picture": "figure", "figure": "figure",
    "table": "table",
    "title": "title", "section-header": "title", "section_header": "title",
    "caption": "caption",
    "list-item": "list", "list": "list",
    "text": "text", "paragraph": "text", "plain text": "text",
}


def map_label(raw: str) -> str:
    return _LABEL_MAP.get(raw.strip().lower(), "text")


class YoloLayoutDetector:
    """Real layout detector. `model_path` is a YOLO/DETR doc-layout checkpoint."""

    def __init__(self, model_path: str, conf: float = 0.3) -> None:
        from ultralytics import YOLO  # type: ignore

        self._model = YOLO(model_path)
        self._conf = conf

    def detect(self, image: Image.Image, page: int) -> list[Region]:
        results = self._model.predict(image, conf=self._conf, verbose=False)
        regions: list[Region] = []
        for res in results:
            names = res.names
            for box in res.boxes:
                x0, y0, x1, y1 = (float(v) for v in box.xyxy[0].tolist())
                kind = map_label(names[int(box.cls)])
                regions.append(Region(kind=kind, bbox=(x0, y0, x1, y1),
                                       page=page, score=float(box.conf)))
        return regions
