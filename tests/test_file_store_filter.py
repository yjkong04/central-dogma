"""FileVectorStore is the rollback backend production /ask passes paper_ids into
(see deploy/README.md 'Aurora vector store' rollback note), but only DemoStore's
paper_ids filtering was covered. Build a tiny FileVectorStore offline (no network,
no torch) and exercise the same filter contract.
"""
import json

from api.embeddings import HashingEmbedder
from api.store import FileVectorStore


def _corpus(tmp_path):
    emb = HashingEmbedder(dim=32)
    recs = [
        {"paper_id": "A", "source_id": "A:c1", "modality": "text", "section": "Results",
         "figure_label": None, "image_uri": None, "text": "alpha beta gamma"},
        {"paper_id": "B", "source_id": "B:c1", "modality": "text", "section": "Results",
         "figure_label": None, "image_uri": None, "text": "alpha delta epsilon"},
        {"paper_id": "A", "source_id": "A:fig1", "modality": "figure", "section": "Results",
         "figure_label": "Figure 1", "image_uri": "https://x/a.jpg", "text": "alpha figure caption"},
        {"paper_id": "B", "source_id": "B:fig1", "modality": "figure", "section": "Results",
         "figure_label": "Figure 1", "image_uri": "https://x/b.jpg", "text": "alpha other caption"},
    ]
    for r in recs:
        r["embedding"] = emb.embed([r["text"]])[0].tolist()
    p = tmp_path / "corpus.json"
    p.write_text(json.dumps({"embedding_model": "hashing", "dim": 32, "records": recs}))
    return str(p), emb


def test_search_text_with_paper_ids_restricts_to_that_paper(tmp_path):
    path, emb = _corpus(tmp_path)
    store = FileVectorStore.from_file(path, emb)
    hits = store.search_text("alpha", k=10, paper_ids=["A"])
    assert hits
    assert {h.record.paper_id for h in hits} == {"A"}


def test_search_text_with_empty_paper_ids_returns_nothing(tmp_path):
    path, emb = _corpus(tmp_path)
    store = FileVectorStore.from_file(path, emb)
    hits = store.search_text("alpha", k=10, paper_ids=[])
    assert hits == []


def test_search_figures_with_paper_ids_restricts_to_that_paper(tmp_path):
    path, emb = _corpus(tmp_path)
    store = FileVectorStore.from_file(path, emb)
    hits = store.search_figures("alpha", k=10, paper_ids=["B"])
    assert hits
    assert {h.record.paper_id for h in hits} == {"B"}
