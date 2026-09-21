import pytest
from botocore.exceptions import ClientError

import api.status_store as ss


class FakeTable:
    """Minimal in-memory stand-in for a DynamoDB Table resource."""
    def __init__(self, name, key_attrs):
        self.name = name
        self.key_attrs = key_attrs          # e.g. ("batch_id",) or ("batch_id", "paper_id")
        self.items = {}                      # key-tuple -> item dict
        self.update_calls = []

    def _key(self, d):
        return tuple(d[a] for a in self.key_attrs)

    def put_item(self, Item):
        self.items[self._key(Item)] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(self._key(Key))
        return {"Item": item} if item is not None else {}

    def query(self, KeyConditionExpression=None, **kw):
        # test uses the low-level shim below; return all papers for a batch_id
        bid = kw.get("_batch_id")
        return {"Items": [v for k, v in self.items.items() if k[0] == bid]}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues=None,
                    ConditionExpression=None, ExpressionAttributeNames=None, **kw):
        self.update_calls.append((UpdateExpression, ExpressionAttributeValues, ConditionExpression))
        item = self.items.setdefault(self._key(Key), dict(Key))
        vals = ExpressionAttributeValues or {}
        # emulate the cap: "SET #t = if_not_exists(#t, :ttl) ADD #n :one" with
        # ConditionExpression "attribute_not_exists(#n) OR #n < :cap"
        if ConditionExpression is not None:
            n = item.get("n")
            cap = vals[":cap"]
            if not (n is None or n < cap):
                raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
            item["n"] = (n or 0) + vals[":one"]
            item.setdefault("ttl", vals[":ttl"])
        else:
            # counter bumps: ADD done :d, failed :f  /  SET state=..., error=...
            for token, val in vals.items():
                attr = token.lstrip(":")
                if attr in ("d", "done"):
                    item["done"] = item.get("done", 0) + val
                elif attr in ("f", "failed"):
                    item["failed"] = item.get("failed", 0) + val
                elif attr == "state":
                    item["state"] = val
                elif attr == "error":
                    item["error"] = val


@pytest.fixture
def tables(monkeypatch):
    batches = FakeTable("batches", ("batch_id",))
    papers = FakeTable("papers", ("batch_id", "paper_id"))
    reg = {"centraldogma-batches": batches, "centraldogma-papers": papers}
    monkeypatch.setattr(ss, "_table", lambda name: reg[name])
    # query() shim: read_batch calls papers.query(...); route the batch_id through
    orig_query = papers.query
    monkeypatch.setattr(papers, "query", lambda **kw: orig_query(_batch_id=kw.get("_batch_id", kw.get("batch_id"))))
    return batches, papers


def test_put_and_read_batch_with_papers(tables, monkeypatch):
    batches, papers = tables
    # make read_batch pass the batch_id into our query shim
    monkeypatch.setattr(ss, "_query_papers", lambda bid: papers.query(_batch_id=bid)["Items"])
    ss.put_batch("b1", created_at="2026-09-15T00:00:00+00:00")
    ss.put_paper("b1", "A", "a.pdf")
    ss.put_paper("b1", "B", "b.pdf")
    out = ss.read_batch("b1")
    assert out["batch"]["batch_id"] == "b1"
    assert {p["paper_id"] for p in out["papers"]} == {"A", "B"}


def test_read_batch_missing_returns_none(tables):
    assert ss.read_batch("nope") is None


def test_bump_counters_and_mark_paper(tables):
    ss.put_batch("b1", created_at="t")
    ss.put_paper("b1", "A", "a.pdf")
    ss.bump_counters("b1", done=1)
    ss.bump_counters("b1", failed=2)
    batches, papers = tables
    assert batches.items[("b1",)]["done"] == 1
    assert batches.items[("b1",)]["failed"] == 2
    ss.mark_paper("b1", "A", "failed", error="boom")
    assert papers.items[("b1", "A")]["state"] == "failed"
    assert papers.items[("b1", "A")]["error"] == "boom"


def test_reserve_upload_slot_allows_up_to_cap_then_rejects(tables):
    ok = [ss.reserve_upload_slot("2026-09-15", cap=3, ttl_epoch=999) for _ in range(4)]
    assert ok == [True, True, True, False]
