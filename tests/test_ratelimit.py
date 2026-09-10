from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.ratelimit import DailyCapMiddleware

def _app(cap):
    app = FastAPI()
    app.add_middleware(DailyCapMiddleware, cap=cap, path="/ask")
    @app.post("/ask")
    def ask(): return {"ok": True}
    @app.get("/health")
    def health(): return {"ok": True}
    return TestClient(app)

def test_blocks_after_cap():
    c = _app(2)
    assert c.post("/ask").status_code == 200
    assert c.post("/ask").status_code == 200
    assert c.post("/ask").status_code == 429

def test_other_paths_not_capped():
    c = _app(0)
    assert c.get("/health").status_code == 200  # cap only applies to /ask
