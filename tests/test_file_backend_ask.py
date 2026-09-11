import importlib, json
import numpy as np
from fastapi.testclient import TestClient
from api.embeddings import HashingEmbedder

def _write_corpus(path):
    emb = HashingEmbedder(dim=64)
    recs = [
        {"paper_id": "P", "source_id": "P:c1", "modality": "text", "section": "Results",
         "figure_label": None, "image_uri": None,
         "text": "response increased with dose then plateaued"},
        {"paper_id": "P", "source_id": "P:c2", "modality": "text", "section": "Methods",
         "figure_label": None, "image_uri": None,
         "text": "samples were treated across a dose series"},
    ]
    for r in recs:
        r["embedding"] = emb.embed([r["text"]])[0].tolist()
    path.write_text(json.dumps({"embedding_model": "hashing", "dim": 64, "records": recs}))

def test_ask_over_file_store(tmp_path, monkeypatch):
    corpus = tmp_path / "demo_corpus.json"; _write_corpus(corpus)
    monkeypatch.setenv("CENTRALDOGMA_STORE_BACKEND", "file")
    monkeypatch.setenv("CENTRALDOGMA_EMBEDDER", "hashing")
    monkeypatch.setenv("CENTRALDOGMA_EMBEDDING_DIM", "64")
    monkeypatch.setenv("CENTRALDOGMA_GENERATOR", "extractive")
    monkeypatch.setenv("CENTRALDOGMA_DEMO_CORPUS_PATH", str(corpus))
    import api.config as cfg; cfg.get_settings.cache_clear()
    import api.main as main; importlib.reload(main)
    client = TestClient(main.app)
    r = client.post("/ask", json={"question": "what happens to response as dose increases"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "answered"
    assert body["backend"] == "file"
    assert len(body["citations"]) >= 1
