from datetime import datetime, timezone

import pytest

import api.uploads as up
from api.config import get_settings


class FakeS3:
    def __init__(self):
        self.calls = []
    def generate_presigned_post(self, Bucket, Key, Fields=None, Conditions=None, ExpiresIn=None):
        self.calls.append({"Bucket": Bucket, "Key": Key, "Conditions": Conditions, "ExpiresIn": ExpiresIn})
        return {"url": f"https://s3/{Bucket}", "fields": {"key": Key}}


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setenv("CENTRALDOGMA_UPLOADS_BUCKET", "cd-uploads")
    get_settings.cache_clear()
    fake_s3 = FakeS3()
    monkeypatch.setattr(up, "_s3", lambda: fake_s3)
    slots = {"n": 0}
    monkeypatch.setattr(up.status_store, "reserve_upload_slot",
                        lambda day, cap, ttl_epoch: (slots.__setitem__("n", slots["n"] + 1) or slots["n"] <= cap))
    monkeypatch.setattr(up.status_store, "put_batch", lambda *a, **k: None)
    yield fake_s3
    get_settings.cache_clear()


def test_create_batch_zip_key_and_size_condition(wired):
    out = up.create_batch("study.zip", "zip", now=NOW)
    assert out["batch_id"]
    assert out["upload"]["fields"]["key"].startswith("uploads/")
    assert out["upload"]["fields"]["key"].endswith(".zip")
    cond = wired.calls[0]["Conditions"][0]
    assert cond == ["content-length-range", 1, 25 * 1_048_576]
    assert wired.calls[0]["ExpiresIn"] == 900


def test_create_batch_pdf_uses_pdf_extension_and_pdf_limit(wired):
    up.create_batch("paper.pdf", "pdf", now=NOW)
    assert wired.calls[0]["Key"].endswith(".pdf")
    assert wired.calls[0]["Conditions"][0][2] == 20 * 1_048_576


def test_create_batch_raises_when_cap_reached(monkeypatch):
    monkeypatch.setattr(up, "_s3", lambda: FakeS3())
    monkeypatch.setattr(up.status_store, "reserve_upload_slot", lambda day, cap, ttl_epoch: False)
    with pytest.raises(up.UploadCapReached):
        up.create_batch("x.zip", "zip", now=NOW)


def test_get_batch_shapes_status(monkeypatch):
    monkeypatch.setattr(up.status_store, "read_batch", lambda bid: {
        "batch": {"batch_id": bid, "state": "pending", "total": 2, "done": 1, "failed": 0},
        "papers": [{"paper_id": "A", "filename": "a.pdf", "state": "done", "error": None}],
    })
    out = up.get_batch("b1")
    assert out["done"] == 1 and out["papers"][0]["paper_id"] == "A"


def test_get_batch_missing_raises(monkeypatch):
    monkeypatch.setattr(up.status_store, "read_batch", lambda bid: None)
    with pytest.raises(up.BatchNotFound):
        up.get_batch("nope")
