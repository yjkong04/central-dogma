from PIL import Image

from ingest.pdf.caption import CaptionTextUnderstander


def test_default_understander_returns_the_detected_caption():
    u = CaptionTextUnderstander()
    assert u.describe(Image.new("RGB", (4, 4)), "Figure 2. Survival curve.") == \
        "Figure 2. Survival curve."


def test_default_understander_empty_caption_stays_empty():
    u = CaptionTextUnderstander()
    assert u.describe(Image.new("RGB", (4, 4)), "") == ""
