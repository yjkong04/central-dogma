import json
import api.store_aurora as sa
from api.store_aurora import AuroraVectorStore


class FakeEmbedder:
    dim = 1024
    def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]


class FakeRds:
    """Records execute_statement calls; returns canned JSON rows."""
    def __init__(self, rows):
        self._rows = rows
        self.calls = []
    def execute_statement(self, **kw):
        self.calls.append(kw)
        return {"formattedRecords": json.dumps(self._rows)}


def _store(fake):
    sa._client = lambda region=None: fake  # monkeypatch factory
    return AuroraVectorStore("arn:cluster", "arn:secret", "cd", FakeEmbedder())


def test_search_text_builds_cosine_sql_and_maps_rows():
    fake = FakeRds([
        {"chunk_id": "A:c0", "paper_id": "A", "section": "Intro",
         "content": "alpha", "score": 0.9},
    ])
    hits = _store(fake).search_text("alpha", k=3)
    assert len(hits) == 1
    assert hits[0].record.source_id == "A:c0"
    assert hits[0].record.paper_id == "A"
    assert hits[0].score == 0.9
    sql = fake.calls[0]["sql"]
    assert "text_chunks" in sql and "<=>" in sql and "LIMIT" in sql
    # query vector passed as a cast string param, not interpolated
    params = {p["name"]: p["value"] for p in fake.calls[0]["parameters"]}
    assert params["qvec"]["stringValue"].startswith("[")
    assert "::vector" in sql


def test_search_text_with_paper_ids_adds_in_clause():
    fake = FakeRds([])
    _store(fake).search_text("alpha", k=3, paper_ids=["A", "B"])
    sql = fake.calls[0]["sql"]
    params = {p["name"]: p["value"] for p in fake.calls[0]["parameters"]}
    assert "paper_id IN (" in sql
    assert params["pid0"]["stringValue"] == "A"
    assert params["pid1"]["stringValue"] == "B"


def test_empty_paper_ids_returns_empty_without_querying():
    fake = FakeRds([{"chunk_id": "x"}])
    hits = _store(fake).search_text("alpha", k=3, paper_ids=[])
    assert hits == [] and fake.calls == []


def test_search_figures_maps_figure_rows():
    fake = FakeRds([
        {"figure_id": "A:fig0", "paper_id": "A", "section": None,
         "figure_label": "Figure 1", "caption": "a plot",
         "image_uri": "http://x/y.webp", "score": 0.8},
    ])
    hits = _store(fake).search_figures("plot", k=3)
    assert hits[0].record.figure_label == "Figure 1"
    assert hits[0].record.image_uri == "http://x/y.webp"
    assert "figures" in fake.calls[0]["sql"]
