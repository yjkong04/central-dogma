"""Pipeline behavior: relevance gate, confidence, section coverage. Offline."""

import api.pipeline as pipeline_mod
from api.config import Settings
from api.pipeline import answer_question
from api.schemas import AskRequest, Modality
from api.store import Record, ScoredRecord


class FakeStore:
    name = "fake"

    def __init__(self, records):
        self._records = records

    def search_text(self, query, k, paper_ids=None):
        return self._records[:k]

    def search_figures(self, query, k, paper_ids=None):
        return []


class _Answering:
    def generate(self, question, citations):
        return "grounded answer"


def _text_hit(sid, section, score):
    return ScoredRecord(Record("P", sid, Modality.TEXT, "some text", section), score)


def test_relevance_gate_refuses_weak_matches(monkeypatch):
    monkeypatch.setattr(pipeline_mod, "get_settings", lambda: Settings(min_relevance_score=0.5))
    store = FakeStore([_text_hit("c1", "Methods", 0.1)])  # below the 0.5 gate
    resp = answer_question(AskRequest(question="anything here?"), store, _Answering())
    assert resp.status == "refused"
    assert resp.citations == []


def test_confidence_and_section_coverage(monkeypatch):
    monkeypatch.setattr(pipeline_mod, "get_settings", lambda: Settings(min_relevance_score=0.0))
    store = FakeStore([_text_hit("c1", "Methods", 0.9), _text_hit("c2", "Results", 0.7)])
    resp = answer_question(AskRequest(question="method and result?"), store, _Answering())
    assert resp.status == "answered"
    assert resp.confidence == 0.9  # top score
    assert resp.sections_covered == 2  # spans Methods + Results (multi-hop)
