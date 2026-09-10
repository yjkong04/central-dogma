import json
import numpy as np
from api.store import FileVectorStore
from api.schemas import Modality

class _StubEmbedder:
    dim = 3
    def __init__(self, q): self._q = np.asarray(q, dtype=np.float32)
    def embed(self, texts): return self._q.reshape(1, -1)

def _corpus(tmp_path):
    data = {"embedding_model": "stub", "dim": 3, "records": [
        {"paper_id": "P", "source_id": "P:c1", "modality": "text", "section": "Results",
         "figure_label": None, "image_uri": None, "text": "alpha", "embedding": [1.0, 0.0, 0.0]},
        {"paper_id": "P", "source_id": "P:c2", "modality": "text", "section": "Methods",
         "figure_label": None, "image_uri": None, "text": "beta", "embedding": [0.0, 1.0, 0.0]},
        {"paper_id": "P", "source_id": "P:fig3", "modality": "figure", "section": "Results",
         "figure_label": "Figure 3", "image_uri": "https://x/f.jpg", "text": "cap", "embedding": [0.0, 0.0, 1.0]},
    ]}
    p = tmp_path / "c.json"; p.write_text(json.dumps(data)); return str(p)

def test_ranks_text_by_cosine(tmp_path):
    store = FileVectorStore.from_file(_corpus(tmp_path), _StubEmbedder([1.0, 0.0, 0.0]))
    hits = store.search_text("q", 2)
    assert [h.record.source_id for h in hits][0] == "P:c1"
    assert all(h.record.modality == Modality.TEXT for h in hits)

def test_figures_only_for_figure_search(tmp_path):
    store = FileVectorStore.from_file(_corpus(tmp_path), _StubEmbedder([0.0, 0.0, 1.0]))
    hits = store.search_figures("q", 2)
    assert [h.record.source_id for h in hits] == ["P:fig3"]

def test_name_is_file(tmp_path):
    assert FileVectorStore.from_file(_corpus(tmp_path), _StubEmbedder([1.0, 0, 0])).name == "file"
