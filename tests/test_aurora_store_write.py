import api.store_aurora as sa
from api.store_aurora import AuroraVectorStore


class FakeEmbedder:
    dim = 1024
    def embed(self, texts):
        return [[0.0] * 1024 for _ in texts]


class FakeRds:
    def __init__(self):
        self.calls = []
        self._tx = "tx-1"
    def begin_transaction(self, **kw):
        self.calls.append(("begin", kw)); return {"transactionId": self._tx}
    def execute_statement(self, **kw):
        self.calls.append(("exec", kw)); return {}
    def batch_execute_statement(self, **kw):
        self.calls.append(("batch", kw)); return {}
    def commit_transaction(self, **kw):
        self.calls.append(("commit", kw)); return {"transactionStatus": "ok"}
    def rollback_transaction(self, **kw):
        self.calls.append(("rollback", kw)); return {}


def _store(fake):
    sa._client = lambda region=None: fake
    return AuroraVectorStore("arn:c", "arn:s", "cd", FakeEmbedder())


def test_upsert_deletes_then_batch_inserts_in_a_transaction():
    fake = FakeRds()
    _store(fake).upsert_paper(
        "A",
        text_records=[{"source_id": "A:c0", "section": "Intro",
                       "text": "alpha", "embedding": [0.1] * 1024}],
        figure_records=[{"source_id": "A:fig0", "section": None,
                         "figure_label": "Figure 1", "image_uri": "u",
                         "text": "cap", "embedding": [0.2] * 1024}],
    )
    kinds = [c[0] for c in fake.calls]
    assert kinds[0] == "begin"
    assert kinds[-1] == "commit"
    # a delete for the paper happened before inserts
    execs = [c for c in fake.calls if c[0] == "exec"]
    assert any("DELETE FROM text_chunks" in c[1]["sql"] for c in execs)
    assert any("DELETE FROM figures" in c[1]["sql"] for c in execs)
    batches = [c for c in fake.calls if c[0] == "batch"]
    assert any("INSERT INTO text_chunks" in c[1]["sql"] for c in batches)
    assert any("INSERT INTO figures" in c[1]["sql"] for c in batches)
    # every call carried the transactionId
    assert all(c[1].get("transactionId") == "tx-1"
               for c in fake.calls if c[0] in ("exec", "batch"))


def test_upsert_rolls_back_on_error():
    class Boom(FakeRds):
        def batch_execute_statement(self, **kw):
            raise RuntimeError("boom")
    fake = Boom()
    try:
        _store(fake).upsert_paper("A",
            text_records=[{"source_id": "A:c0", "section": None,
                           "text": "x", "embedding": [0.0] * 1024}],
            figure_records=[])
    except RuntimeError:
        pass
    assert any(c[0] == "rollback" for c in fake.calls)
