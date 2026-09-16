from fastapi.testclient import TestClient
from botocore.exceptions import ClientError

import api.main as main
import api.uploads as up
from api.main import app

client = TestClient(app)


def test_post_uploads_returns_presigned_post(monkeypatch):
    monkeypatch.setattr(main.uploads, "create_batch",
                        lambda filename, kind, *, now: {"batch_id": "b1",
                                                        "upload": {"url": "https://s3", "fields": {"key": "uploads/b1.zip"}}})
    resp = client.post("/uploads", json={"filename": "study.zip", "kind": "zip"})
    assert resp.status_code == 200
    assert resp.json()["batch_id"] == "b1"
    assert resp.json()["upload"]["fields"]["key"] == "uploads/b1.zip"


def test_post_uploads_cap_returns_429(monkeypatch):
    def _boom(filename, kind, *, now):
        raise up.UploadCapReached("nope")
    monkeypatch.setattr(main.uploads, "create_batch", _boom)
    assert client.post("/uploads", json={"filename": "x.zip"}).status_code == 429


def test_post_uploads_dynamo_down_returns_503(monkeypatch):
    def _boom(filename, kind, *, now):
        raise ClientError({"Error": {"Code": "InternalServerError"}}, "PutItem")
    monkeypatch.setattr(main.uploads, "create_batch", _boom)
    assert client.post("/uploads", json={"filename": "x.zip"}).status_code == 503


def test_get_batch_200_and_404(monkeypatch):
    monkeypatch.setattr(main.uploads, "get_batch",
                        lambda bid: {"batch_id": bid, "state": "pending", "total": 1,
                                     "done": 0, "failed": 0,
                                     "papers": [{"paper_id": "A", "filename": "a.pdf",
                                                 "state": "pending", "error": None}]})
    assert client.get("/batches/b1").status_code == 200

    def _missing(bid):
        raise up.BatchNotFound(bid)
    monkeypatch.setattr(main.uploads, "get_batch", _missing)
    assert client.get("/batches/nope").status_code == 404
