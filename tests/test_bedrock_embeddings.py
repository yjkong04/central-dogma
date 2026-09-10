import io, json
import numpy as np
import api.embeddings as emb

class _FakeBody:
    def __init__(self, payload): self._b = json.dumps(payload).encode()
    def read(self): return self._b

class _FakeBedrock:
    def __init__(self, vec): self._vec = vec; self.calls = []
    def invoke_model(self, modelId, body):
        self.calls.append((modelId, json.loads(body)))
        return {"body": _FakeBody({"embedding": self._vec})}

def test_bedrock_embedder_calls_titan_and_normalizes(monkeypatch):
    fake = _FakeBedrock([3.0, 0.0, 4.0, 0.0])  # norm 5
    monkeypatch.setattr(emb, "_boto3_client", lambda region: fake)
    e = emb.BedrockEmbedder("amazon.titan-embed-text-v2:0", "us-east-1", dim=4)
    out = e.embed(["hello"])
    assert out.shape == (1, 4)
    np.testing.assert_allclose(np.linalg.norm(out[0]), 1.0, atol=1e-6)
    assert fake.calls[0][1]["inputText"] == "hello"
    assert fake.calls[0][1]["dimensions"] == 4

def test_build_embedder_bedrock(monkeypatch):
    monkeypatch.setattr(emb, "_boto3_client", lambda region: _FakeBedrock([1.0, 0.0]))
    e = emb.build_embedder("bedrock", "amazon.titan-embed-text-v2:0", 2)
    assert isinstance(e, emb.BedrockEmbedder)
