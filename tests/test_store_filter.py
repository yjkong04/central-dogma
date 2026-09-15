from api.store import DemoStore, Record
from api.schemas import Modality


def _store():
    recs = [
        Record(paper_id="A", source_id="A:c0", modality=Modality.TEXT, text="alpha beta"),
        Record(paper_id="B", source_id="B:c0", modality=Modality.TEXT, text="alpha gamma"),
    ]
    return DemoStore(records=recs)


def test_search_text_without_filter_searches_all_papers():
    hits = _store().search_text("alpha", k=10)
    assert {h.record.paper_id for h in hits} == {"A", "B"}


def test_search_text_with_paper_ids_filter_restricts():
    hits = _store().search_text("alpha", k=10, paper_ids=["A"])
    assert {h.record.paper_id for h in hits} == {"A"}


def test_empty_paper_ids_list_matches_nothing():
    hits = _store().search_text("alpha", k=10, paper_ids=[])
    assert hits == []
