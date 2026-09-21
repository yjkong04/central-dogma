import json

import pytest

import worker.handler as wh
from ingest.pmc import Figure, ParsedPaper, Section


class FakeS3:
    def __init__(self, body=b"%PDF"):
        self._body = body
    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self._body)}


class FakeEmbedder:
    def embed(self, texts):
        return [[0.0] * 4 for _ in texts]


class FakeStore:
    def __init__(self):
        self.upserts = []
    def upsert_paper(self, paper_id, text_records, figure_records):
        self.upserts.append((paper_id, text_records, figure_records))


class RecordingStatus:
    """Fake status_store that enforces the same idempotency contract as the
    real DynamoDB-backed mark_paper: once a (batch_id, paper_id) is marked
    "done" or "failed", further mark_paper calls for it are no-ops that
    return False -- so callers relying on the return value to gate
    bump_counters are exercised honestly, not just called through blindly.
    """
    def __init__(self):
        self.marks, self.bumps = [], []
        self._terminal = {}
    def mark_paper(self, batch_id, paper_id, state, error=None):
        self.marks.append((batch_id, paper_id, state, error))
        key = (batch_id, paper_id)
        if key in self._terminal:
            return False
        if state in ("done", "failed"):
            self._terminal[key] = state
        return True
    def bump_counters(self, batch_id, *, done=0, failed=0):
        self.bumps.append((batch_id, done, failed))


MSG = {"batch_id": "B1", "paper_key": "papers/B1/0.pdf",
       "paper_id": "batch-B1-0", "filename": "a.pdf"}


def _paper():
    return ParsedPaper(paper_id="pdf-abc", title="t",
                       sections=[Section(title="Intro", text="hello world")],
                       figures=[Figure(label="Figure 1", caption="c", image_bytes=b"PNG")])


@pytest.fixture
def wired(monkeypatch, tmp_path):
    status = RecordingStatus()
    store = FakeStore()
    monkeypatch.setattr(wh, "status_store", status)
    monkeypatch.setattr(wh, "_s3", lambda: FakeS3())
    monkeypatch.setattr(wh, "_layout_detector", lambda: object())
    monkeypatch.setattr(wh, "_get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(wh, "_get_store", lambda: store)
    monkeypatch.setattr(wh, "parse_pdf", lambda path, **kw: _paper())
    # ensure_fig_ids, chunk_paper, build_records, store_crops run for real over the fake paper;
    # store_crops needs an s3 — it receives wh._s3(); FakeS3 has no put_object, so fake store_crops:
    monkeypatch.setattr(wh, "store_crops", lambda pid, figs, s3, bucket, base: {"fig0": "https://cdn/figures/pdf-abc/fig0.png"})
    monkeypatch.setenv("CENTRALDOGMA_FIGURES_BASE_URL", "https://cdn")
    from api.config import get_settings
    get_settings.cache_clear()
    yield status, store
    get_settings.cache_clear()


def test_happy_path_upserts_and_marks_done(wired):
    status, store = wired
    wh.handler({"Records": [{"body": json.dumps(MSG)}]}, None)
    assert len(store.upserts) == 1
    pid, text_records, figure_records = store.upserts[0]
    assert pid == "pdf-abc"                          # content id, from parse_pdf
    assert figure_records[0]["image_uri"] == "https://cdn/figures/pdf-abc/fig0.png"
    assert status.marks == [("B1", "batch-B1-0", "done", None)]   # status id from the message
    assert status.bumps == [("B1", 1, 0)]


def test_failure_marks_failed_and_reraises(wired, monkeypatch):
    status, store = wired
    monkeypatch.setattr(wh, "parse_pdf", lambda path, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        wh.handler({"Records": [{"body": json.dumps(MSG)}]}, None)
    assert status.marks == [("B1", "batch-B1-0", "failed", "boom")]
    assert status.bumps == [("B1", 0, 1)]
    assert store.upserts == []


def test_redelivered_message_does_not_double_bump_counters(wired):
    # simulates SQS at-least-once redelivery: the same message is processed
    # twice (e.g. a near-deadline invocation that still succeeded but got
    # redelivered anyway). The second _ingest_one call must still upsert to
    # Aurora (idempotent there) but must NOT bump the batch counters again,
    # since mark_paper is a no-op the second time around.
    status, store = wired
    msg = json.loads(json.dumps(MSG))
    wh._ingest_one(msg)
    wh._ingest_one(msg)
    assert len(store.upserts) == 2
    assert status.marks == [
        ("B1", "batch-B1-0", "done", None),
        ("B1", "batch-B1-0", "done", None),
    ]
    assert status.bumps == [("B1", 1, 0)]


def test_redelivered_failure_does_not_double_bump_counters(wired, monkeypatch):
    status, store = wired
    monkeypatch.setattr(wh, "parse_pdf", lambda path, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    msg = json.loads(json.dumps(MSG))
    for _ in range(2):
        with pytest.raises(RuntimeError):
            wh._ingest_one(msg)
    assert status.marks == [
        ("B1", "batch-B1-0", "failed", "boom"),
        ("B1", "batch-B1-0", "failed", "boom"),
    ]
    assert status.bumps == [("B1", 0, 1)]
    assert store.upserts == []
