from ingest.pmc import Figure, ParsedPaper, Section
from ingest.chunk import chunk_paper
from ingest.pipeline_records import build_records
from ingest.crops import ensure_fig_ids, store_crops


class FakeS3:
    def __init__(self):
        self.puts = []
    def put_object(self, **kw):
        self.puts.append(kw)
        return {}


def test_ensure_fig_ids_fills_none_and_preserves_existing():
    paper = ParsedPaper(paper_id="P", title="t", figures=[
        Figure(label="Figure 1", caption="c0"),                    # fig_id None
        Figure(label="Figure 2", caption="c1", fig_id="jats-7"),   # keep
    ])
    ensure_fig_ids(paper)
    assert [f.fig_id for f in paper.figures] == ["fig0", "jats-7"]


def test_store_crops_uploads_bytes_and_returns_urls():
    figs = [
        Figure(label="F1", caption="c", fig_id="fig0", image_bytes=b"PNGDATA"),
        Figure(label="F2", caption="c", fig_id="fig1"),  # no bytes -> skipped
    ]
    s3 = FakeS3()
    urls = store_crops("P", figs, s3, bucket="figs-bucket", base_url="https://cdn.example")
    assert urls == {"fig0": "https://cdn.example/figures/P/fig0.png"}
    assert len(s3.puts) == 1
    put = s3.puts[0]
    assert put["Bucket"] == "figs-bucket"
    assert put["Key"] == "figures/P/fig0.png"
    assert put["Body"] == b"PNGDATA"
    assert put["ContentType"] == "image/png"


def test_pdf_figure_crop_carries_through_to_the_record():
    # A parse_pdf-shaped figure: fig_id None, has crop bytes, no image_uri.
    paper = ParsedPaper(paper_id="P", title="t",
                        sections=[Section(title="Intro", text="body text")],
                        figures=[Figure(label="Figure 1", caption="a cell",
                                        image_bytes=b"PNG")])
    ensure_fig_ids(paper)                       # -> fig0
    s3 = FakeS3()
    crop_urls = store_crops(paper.paper_id, paper.figures, s3,
                            bucket="b", base_url="https://cdn")
    chunks = chunk_paper(paper)
    embeddings = [[0.0] for _ in chunks]        # dummy, one dim
    _text, figure_records = build_records(paper, chunks, embeddings, crop_urls)
    assert figure_records[0]["image_uri"] == "https://cdn/figures/P/fig0.png"
