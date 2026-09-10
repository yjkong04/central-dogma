import json
import api.generation as gen
from api.schemas import Citation, Modality

class _Body:
    def __init__(self, p): self._b = json.dumps(p).encode()
    def read(self): return self._b

class _FakeClaude:
    def __init__(self, text): self._text = text; self.calls = []
    def invoke_model(self, modelId, body):
        self.calls.append(json.loads(body))
        return {"body": _Body({"content": [{"type": "text", "text": self._text}]})}

def _text_citation():
    return Citation(modality=Modality.TEXT, paper_id="P", source_id="P:c1", section="Results",
                    figure_label=None, image_uri=None, snippet="response rose then plateaued", score=0.8)

def test_generates_inline_cited_answer(monkeypatch):
    fake = _FakeClaude("Response rises then plateaus [Results].")
    monkeypatch.setattr(gen, "_boto3_client", lambda region: fake)
    g = gen.BedrockGenerator("anthropic.claude-3-5-haiku-20241022-v1:0", "us-east-1")
    out = g.generate("what happens with dose?", [_text_citation()])
    assert out == "Response rises then plateaus [Results]."
    body = fake.calls[0]
    assert body["system"] == gen._SYSTEM
    assert body["messages"][0]["role"] == "user"

def test_no_answer_becomes_refusal(monkeypatch):
    monkeypatch.setattr(gen, "_boto3_client", lambda region: _FakeClaude("NO_ANSWER"))
    g = gen.BedrockGenerator("anthropic.claude-3-5-haiku-20241022-v1:0", "us-east-1")
    assert g.generate("unrelated", [_text_citation()]) == ""
