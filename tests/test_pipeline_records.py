import pytest

from ingest.chunk import Chunk
from ingest.pmc import ParsedPaper
from ingest.pipeline_records import build_records


def _text(cid, ordv, content="alpha", section="Intro"):
    return Chunk(chunk_id=cid, paper_id="A", modality="text",
                 section=section, content=content, ord=ordv)


def _fig(cid, ordv, fig_id, label="Figure 1", content="cap", image_uri=None):
    return Chunk(chunk_id=cid, paper_id="A", modality="figure", section=None,
                 content=content, figure_label=label, fig_id=fig_id,
                 image_uri=image_uri, ord=ordv)


def test_text_and_figure_split_and_shape():
    paper = ParsedPaper(paper_id="A", title="t")
    chunks = [_text("A:c0", 0), _fig("A:fig0", 1, "f0")]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    text_records, figure_records = build_records(paper, chunks, embeddings)
    assert text_records == [
        {"source_id": "A:c0", "section": "Intro", "content": "alpha", "embedding": [0.1, 0.2]}
    ]
    assert figure_records == [
        {"source_id": "A:fig0", "section": None, "figure_label": "Figure 1",
         "content": "cap", "image_uri": None, "embedding": [0.3, 0.4]}
    ]


def test_figure_image_uri_joined_from_crop_urls_by_fig_id():
    paper = ParsedPaper(paper_id="A", title="t")
    chunks = [_fig("A:fig0", 0, "f0")]
    figure_records = build_records(paper, chunks, [[0.0]], crop_urls={"f0": "s3://x/f0.png"})[1]
    assert figure_records[0]["image_uri"] == "s3://x/f0.png"


def test_crop_urls_take_precedence_but_fall_back_to_chunk_image_uri():
    paper = ParsedPaper(paper_id="A", title="t")
    chunks = [_fig("A:fig0", 0, "f0", image_uri="https://cdn/pmc.png")]
    # fig_id not in crop_urls -> fall back to the chunk's existing (PMC) uri
    figure_records = build_records(paper, chunks, [[0.0]], crop_urls={"other": "u"})[1]
    assert figure_records[0]["image_uri"] == "https://cdn/pmc.png"


def test_caption_less_figure_still_produces_a_record():
    paper = ParsedPaper(paper_id="A", title="t")
    chunks = [_fig("A:fig0", 0, "f0", label="Figure 2", content="Figure 2")]
    figure_records = build_records(paper, chunks, [[0.0]])[1]
    assert figure_records[0]["content"] == "Figure 2"


def test_length_mismatch_raises():
    paper = ParsedPaper(paper_id="A", title="t")
    with pytest.raises(ValueError):
        build_records(paper, [_text("A:c0", 0)], embeddings=[])
