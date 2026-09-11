import json
import numpy as np
from scripts.build_demo_corpus import build


class _FakeEmbedder:
    dim = 4

    def embed(self, texts):
        return np.tile(np.arange(4, dtype=np.float32), (len(texts), 1))


class _Chunk:
    """Mirrors the real ingest.chunk.Chunk field names (chunk_id/content, not
    source_id/text) so this test genuinely exercises the ingest -> JSON mapping."""

    def __init__(self, chunk_id, paper_id, modality, section, content,
                 figure_label=None, image_uri=None):
        self.chunk_id = chunk_id
        self.paper_id = paper_id
        self.modality = modality
        self.section = section
        self.content = content
        self.figure_label = figure_label
        self.image_uri = image_uri


class _Paper:
    paper_id = "PMC1"
    title = "t"


def test_build_writes_json(tmp_path, monkeypatch):
    import scripts.build_demo_corpus as m

    monkeypatch.setattr(m, "fetch_and_parse", lambda pmcid: _Paper())
    monkeypatch.setattr(m, "attach_figure_image_urls", lambda paper: 0)
    monkeypatch.setattr(m, "chunk_paper", lambda paper: [
        _Chunk("PMC1:c1", "PMC1", "text", "Results", "alpha"),
        _Chunk("PMC1:fig1", "PMC1", "figure", "Results", "a caption", "Figure 1", "https://x/f.jpg"),
    ])

    out = tmp_path / "demo_corpus.json"
    build(["PMC1"], _FakeEmbedder(), str(out))

    data = json.loads(out.read_text())
    assert data["dim"] == 4 and len(data["records"]) == 2
    r0 = data["records"][0]
    assert set(r0) >= {"paper_id", "source_id", "modality", "section", "figure_label", "image_uri", "text", "embedding"}
    assert len(r0["embedding"]) == 4
    assert r0["paper_id"] == "PMC1"
    assert r0["source_id"] == "PMC1:c1"
    assert r0["text"] == "alpha"

    r1 = data["records"][1]
    assert r1["source_id"] == "PMC1:fig1"
    assert r1["modality"] == "figure"
    assert r1["figure_label"] == "Figure 1"
    assert r1["image_uri"] == "https://x/f.jpg"
    assert r1["text"] == "a caption"
