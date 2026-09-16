"""FastAPI entrypoint.

Run: uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from botocore.exceptions import ClientError

from .config import get_settings
from .generation import Generator, build_generator
from .pipeline import answer_question
from .ratelimit import DailyCapMiddleware
from .schemas import AskRequest, AskResponse, UploadRequest, UploadResponse, BatchStatusResponse
from .store import DemoStore, PgVectorStore, Store
from .store_aurora import StoreUnavailable
from . import uploads
from .uploads import UploadCapReached, BatchNotFound

logger = logging.getLogger("centraldogma.api")

app = FastAPI(
    title="Central Dogma",
    version="0.1.0",
    description="Multi-modal RAG over scientific papers: cited answers over text and figures.",
)


@app.exception_handler(StoreUnavailable)
async def _store_unavailable_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc) or "vector store is warming up; please retry shortly"},
    )


@app.exception_handler(UploadCapReached)
async def _upload_cap_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": str(exc) or "daily upload limit reached"})


@app.exception_handler(BatchNotFound)
async def _batch_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": f"batch {exc} not found"})


@app.exception_handler(ClientError)
async def _aws_client_error_handler(request, exc):
    # App-wide: also covers /ask. A boto3 fault degrades to 503 (not 500);
    # log it so a real IAM/config error isn't silently masked as "transient".
    logger.exception("AWS ClientError on %s", request.url.path)
    return JSONResponse(status_code=503, content={"detail": "storage temporarily unavailable; retry shortly"})


def _build_embedder():
    from .embeddings import build_embedder

    settings = get_settings()
    _emb_model = (
        settings.bedrock_embedding_model
        if settings.embedder == "bedrock"
        else settings.embedding_model
    )
    return build_embedder(settings.embedder, _emb_model, settings.embedding_dim)


def _build_store() -> Store:
    settings = get_settings()
    if settings.store_backend == "demo":
        return DemoStore()
    if settings.store_backend == "pgvector":
        embedder = _build_embedder()
        return PgVectorStore(settings.database_url, embedder)
    if settings.store_backend == "file":
        from .store import FileVectorStore

        embedder = _build_embedder()
        return FileVectorStore.from_file(settings.demo_corpus_path, embedder)
    if settings.store_backend == "aurora":
        from .store_aurora import AuroraVectorStore

        embedder = _build_embedder()
        return AuroraVectorStore(
            settings.aurora_cluster_arn,
            settings.aurora_secret_arn,
            settings.aurora_database,
            embedder,
            dim=settings.embedding_dim,
            region=settings.aws_region,
        )
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


@app.post("/uploads", response_model=UploadResponse)
def create_upload(req: UploadRequest) -> UploadResponse:
    result = uploads.create_batch(req.filename, req.kind, now=datetime.now(timezone.utc))
    return UploadResponse(**result)


@app.get("/batches/{batch_id}", response_model=BatchStatusResponse)
def get_batch_status(batch_id: str) -> BatchStatusResponse:
    return BatchStatusResponse(**uploads.get_batch(batch_id))
