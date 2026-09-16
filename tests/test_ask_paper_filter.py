from api.pipeline import answer_question
from api.schemas import AskRequest


class SpyStore:
    name = "spy"

    def __init__(self):
        self.seen = []

    def search_text(self, query, k, paper_ids=None):
        self.seen.append(("text", paper_ids))
        return []

    def search_figures(self, query, k, paper_ids=None):
        self.seen.append(("figure", paper_ids))
        return []


class DummyGen:
    def generate(self, *a, **k):  # matches Generator protocol used by answer_question
        return ""


def test_paper_id_is_forwarded_as_filter():
    store = SpyStore()
    answer_question(AskRequest(question="what is x?", paper_id="PMC123"), store, DummyGen())
    assert ("text", ["PMC123"]) in store.seen
    assert ("figure", ["PMC123"]) in store.seen


def test_no_paper_id_searches_all():
    store = SpyStore()
    answer_question(AskRequest(question="what is x?"), store, DummyGen())
    assert ("text", None) in store.seen
