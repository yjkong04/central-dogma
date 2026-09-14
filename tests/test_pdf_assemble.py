from PIL import Image

from ingest.pdf.assemble import assemble
from ingest.pdf.caption import CaptionTextUnderstander
from ingest.pdf.types import Page, Region, TextBlock


def _page(w=100, h=100):
    return Page(index=0, image=Image.new("RGB", (w, h), "white"))


def _tb(text, y0, y1, page=0):
    return TextBlock(text=text, bbox=(0, y0, 100, y1), page=page)


def test_sections_group_text_under_titles_in_reading_order():
    pages = [_page()]
    text = [_tb("Introduction", 0, 10), _tb("We study X.", 10, 20),
            _tb("Methods", 40, 50), _tb("We did Y.", 50, 60)]
    regions = [Region("title", (0, 0, 100, 10), 0), Region("text", (0, 10, 100, 20), 0),
               Region("title", (0, 40, 100, 50), 0), Region("text", (0, 50, 100, 60), 0)]
    paper = assemble("pdf-abc", "My Paper", pages, {0: text}, {0: regions},
                     CaptionTextUnderstander())
    assert paper.paper_id == "pdf-abc" and paper.title == "My Paper"
    titles = [s.title for s in paper.sections]
    assert titles == ["Introduction", "Methods"]
    assert "We study X." in paper.sections[0].text
    assert "We did Y." in paper.sections[1].text


def test_figure_region_produces_a_figure_with_crop_and_nearest_caption():
    pages = [_page()]
    regions = [Region("figure", (10, 10, 60, 60), 0),
               Region("caption", (10, 62, 60, 70), 0)]
    text = [_tb("Figure 1. A scatter plot.", 62, 70)]
    paper = assemble("pdf-abc", None, pages, {0: text}, {0: regions},
                     CaptionTextUnderstander())
    assert len(paper.figures) == 1
    fig = paper.figures[0]
    assert fig.caption == "Figure 1. A scatter plot."
    assert fig.label == "Figure 1"
    assert isinstance(fig.image_bytes, bytes) and len(fig.image_bytes) > 0


def test_caption_less_figure_still_embeddable():
    pages = [_page()]
    regions = [Region("figure", (10, 10, 60, 60), 0)]
    paper = assemble("pdf-abc", None, pages, {0: []}, {0: regions},
                     CaptionTextUnderstander())
    assert len(paper.figures) == 1
    assert paper.figures[0].caption  # non-empty fallback ("figure")
