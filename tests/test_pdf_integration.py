import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

MODEL = os.environ.get("CD_LAYOUT_MODEL")  # path to a YOLO/DETR layout checkpoint
REAL_PDF = Path("tests/fixtures/pdf/real_sample.pdf")  # add locally; not committed if large


@pytest.mark.skipif(not MODEL or not REAL_PDF.exists(),
                    reason="set CD_LAYOUT_MODEL and add tests/fixtures/pdf/real_sample.pdf")
def test_real_pipeline_end_to_end():
    from ingest.chunk import chunk_paper
    from ingest.pdf.layout import YoloLayoutDetector
    from ingest.pdf.parse import parse_pdf

    paper = parse_pdf(REAL_PDF, layout=YoloLayoutDetector(MODEL))
    chunks = chunk_paper(paper)
    assert paper.sections, "real paper should yield sections"
    assert any(c.modality == "text" for c in chunks)
    # figures are paper-dependent; assert crops are real bytes when present
    for f in paper.figures:
        assert f.image_bytes and len(f.image_bytes) > 100
