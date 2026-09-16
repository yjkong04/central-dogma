import io
import json
import zipfile

import pytest

import worker.dispatcher as disp
from api.config import get_settings


class FakeS3:
    def __init__(self, body: bytes):
        self._body = body
        self.puts = []
    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self._body)}
    def put_object(self, **kw):
        self.puts.append(kw)
        return {}


class FakeSqs:
    def __init__(self):
        self.sent = []
    def send_message(self, QueueUrl, MessageBody):
        self.sent.append((QueueUrl, json.loads(MessageBody)))
        return {}


class RecordingStore:
    def __init__(self):
        self.papers, self.totals, self.failed = [], [], []
    def put_paper(self, batch_id, paper_id, filename, state="pending"):
        self.papers.append((batch_id, paper_id, filename))
    def set_batch_total(self, batch_id, total, state="running"):
        self.totals.append((batch_id, total, state))
    def mark_batch_failed(self, batch_id, error):
        self.failed.append((batch_id, error))


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return buf.getvalue()


def _event(key):
    return {"Records": [{"s3": {"bucket": {"name": "up"}, "object": {"key": key}}}]}


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setenv("CENTRALDOGMA_UPLOADS_QUEUE_URL", "https://sqs/q")
    get_settings.cache_clear()
    store = RecordingStore()
    monkeypatch.setattr(disp, "status_store", store)
    sqs = FakeSqs()
    monkeypatch.setattr(disp, "_sqs", lambda: sqs)
    yield store, sqs
    get_settings.cache_clear()


def test_zip_event_fans_out_per_pdf(wired, monkeypatch):
    store, sqs = wired
    s3 = FakeS3(_zip({"a.pdf": b"A", "b.pdf": b"B"}))
    monkeypatch.setattr(disp, "_s3", lambda: s3)
    disp.handler(_event("uploads/B1.zip"), None)
    assert [p[1] for p in store.papers] == ["batch-B1-0", "batch-B1-1"]
    assert [k["Key"] for k in s3.puts] == ["papers/B1/0.pdf", "papers/B1/1.pdf"]
    assert [m[1]["paper_key"] for m in sqs.sent] == ["papers/B1/0.pdf", "papers/B1/1.pdf"]
    assert sqs.sent[0][0] == "https://sqs/q"
    assert store.totals == [("B1", 2, "running")]
    assert store.failed == []


def test_single_pdf_event_is_batch_of_one(wired, monkeypatch):
    store, sqs = wired
    s3 = FakeS3(b"%PDF-1.7")
    monkeypatch.setattr(disp, "_s3", lambda: s3)
    disp.handler(_event("uploads/B2.pdf"), None)
    assert store.totals == [("B2", 1, "running")]
    assert len(sqs.sent) == 1


def test_invalid_zip_marks_batch_failed_and_sends_nothing(wired, monkeypatch):
    store, sqs = wired
    s3 = FakeS3(_zip({"readme.txt": b"x"}))  # no PDFs -> EmptyBatch
    monkeypatch.setattr(disp, "_s3", lambda: s3)
    disp.handler(_event("uploads/B3.zip"), None)
    assert store.failed and store.failed[0][0] == "B3"
    assert sqs.sent == [] and s3.puts == []
    assert store.totals == []
