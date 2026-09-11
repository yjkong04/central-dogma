"""FastAPI entrypoint.

Run: uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .generation import Generator, build_generator
from .pipeline import answer_question
from .ratelimit import DailyCapMiddleware
from .schemas import AskRequest, AskResponse
from .store import DemoStore, PgVectorStore, Store

app = FastAPI(
    title="Central Dogma",
    version="0.1.0",
    description="Multi-modal RAG over scientific papers: cited answers over text and figures.",
)


def _build_store() -> Store:
    settings = get_settings()
    if settings.store_backend == "demo":
        return DemoStore()
    if settings.store_backend == "pgvector":
        from .embeddings import build_embedder

        _emb_model = (
            settings.bedrock_embedding_model
            if settings.embedder == "bedrock"
            else settings.embedding_model
        )
        embedder = build_embedder(settings.embedder, _emb_model, settings.embedding_dim)
        return PgVectorStore(settings.database_url, embedder)
    if settings.store_backend == "file":
        from .embeddings import build_embedder
        from .store import FileVectorStore

        _emb_model = (
            settings.bedrock_embedding_model
            if settings.embedder == "bedrock"
            else settings.embedding_model
        )
        embedder = build_embedder(settings.embedder, _emb_model, settings.embedding_dim)
        return FileVectorStore.from_file(settings.demo_corpus_path, embedder)
    raise RuntimeError(f"unknown store_backend={settings.store_backend!r}")


def _build_generator() -> Generator:
    settings = get_settings()
    # Building qwen-vision loads the model once, at startup, so /ask stays warm.
    model = (
        settings.bedrock_generation_model
        if settings.generator == "bedrock"
        else settings.vision_model
    )
    return build_generator(settings.generator, model)


# Built once for the process. The pgvector store holds the DB connection; the
# generator holds the (heavy) model when qwen-vision is selected.
_store: Store = _build_store()
_generator: Generator = _build_generator()

_settings = get_settings()
app.add_middleware(DailyCapMiddleware, cap=_settings.demo_daily_cap, path="/ask")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.allowed_origins.split(",") if o.strip()],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": _store.name, "generator": get_settings().generator}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    return answer_question(req, _store, _generator)
