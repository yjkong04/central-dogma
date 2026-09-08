"""FastAPI entrypoint.

Run: uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from .config import get_settings
from .generation import Generator, build_generator
from .pipeline import answer_question
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

        embedder = build_embedder(
            settings.embedder, settings.embedding_model, settings.embedding_dim
        )
        return PgVectorStore(settings.database_url, embedder)
    raise RuntimeError(f"unknown store_backend={settings.store_backend!r}")


def _build_generator() -> Generator:
    settings = get_settings()
    # Building qwen-vision loads the model once, at startup, so /ask stays warm.
    return build_generator(settings.generator, settings.vision_model)


# Built once for the process. The pgvector store holds the DB connection; the
# generator holds the (heavy) model when qwen-vision is selected.
_store: Store = _build_store()
_generator: Generator = _build_generator()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": _store.name, "generator": get_settings().generator}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    return answer_question(req, _store, _generator)
