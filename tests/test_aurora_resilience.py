import json

import pytest
from botocore.exceptions import ClientError

import api.store_aurora as sa
from api.store_aurora import AuroraVectorStore, StoreUnavailable


class FakeEmbedder:
    dim = 1024
    def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]


def _resuming_error():
    return ClientError(
        {"Error": {"Code": "DatabaseResumingException", "Message": "resuming"}},
        "ExecuteStatement",
    )


class FlakyThenOkRds:
    """Raises DatabaseResumingException twice, then succeeds."""

    def __init__(self, fail_times):
        self._fail_times = fail_times
        self.calls = 0

    def execute_statement(self, **kw):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise _resuming_error()
        return {"formattedRecords": json.dumps([])}


class AlwaysResumingRds:
    def execute_statement(self, **kw):
        raise _resuming_error()


def _store(fake):
    sa._client = lambda region=None: fake
    return AuroraVectorStore("arn:c", "arn:s", "cd", FakeEmbedder())


def test_search_text_retries_through_resuming_then_succeeds(monkeypatch):
    monkeypatch.setattr(sa, "_SLEEP", lambda *_: None)
    fake = FlakyThenOkRds(fail_times=2)
    hits = _store(fake).search_text("alpha", k=3)
    assert hits == []
    assert fake.calls == 3


def test_search_text_raises_store_unavailable_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(sa, "_SLEEP", lambda *_: None)
    fake = AlwaysResumingRds()
    with pytest.raises(StoreUnavailable):
        _store(fake).search_text("alpha", k=3)
