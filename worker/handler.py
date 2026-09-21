# worker/handler.py
"""SQS-triggered ingestion worker: one PDF message -> parsed, embedded, crops
stored, upserted to Aurora, status flipped.

Every model/AWS dependency is reached through a module-level factory or a
module-level name so the orchestration is unit-testable offline. A terminal
failure marks the paper failed and re-raises so SQS retries -> DLQ.
"""

from __future__ import annotations

import json

import boto3

from api import status_store
from api.config import get_settings
from api.embeddings import build_embedder
from api.store_aurora import AuroraVectorStore
from ingest.chunk import chunk_paper
from ingest.crops import ensure_fig_ids, store_crops
from ingest.pdf import parse_pdf
from ingest.pdf.layout import YoloLayoutDetector
from ingest.pipeline_records import build_records

_s3_client = None
_layout = None
_embedder = None
_store = None


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=get_settings().aws_region)
    return _s3_client


def _layout_detector():
    global _layout
    if _layout is None:
        _layout = YoloLayoutDetector(get_settings().layout_checkpoint_path)
    return _layout


def _get_embedder():
    global _embedder
    if _embedder is None:
        s = get_settings()
        _embedder = build_embedder(s.embedder, s.bedrock_embedding_model, s.embedding_dim)
    return _embedder


def _get_store():
    global _store
    if _store is None:
        s = get_settings()
        _store = AuroraVectorStore(s.aurora_cluster_arn, s.aurora_secret_arn,
                                   s.aurora_database, _get_embedder(),
                                   dim=s.embedding_dim, region=s.aws_region)
    return _store


def _ingest_one(msg: dict) -> None:
    s = get_settings()
    batch_id, status_id = msg["batch_id"], msg["paper_id"]
    try:
        obj = _s3().get_object(Bucket=s.uploads_bucket, Key=msg["paper_key"])
        with open("/tmp/paper.pdf", "wb") as fh:
            fh.write(obj["Body"].read())
        paper = parse_pdf("/tmp/paper.pdf", layout=_layout_detector())
        ensure_fig_ids(paper)
        chunks = chunk_paper(paper)
        embeddings = _get_embedder().embed([c.content for c in chunks])
        crop_urls = store_crops(paper.paper_id, paper.figures, _s3(),
                                s.figures_bucket, s.figures_base_url)
        text_records, figure_records = build_records(paper, chunks, embeddings, crop_urls)
        _get_store().upsert_paper(paper.paper_id, text_records, figure_records)
        if status_store.mark_paper(batch_id, status_id, "done"):
            status_store.bump_counters(batch_id, done=1)
    except Exception as exc:
        if status_store.mark_paper(batch_id, status_id, "failed", error=str(exc)):
            status_store.bump_counters(batch_id, failed=1)
        raise


def handler(event, context) -> None:
    for record in event.get("Records", []):
        _ingest_one(json.loads(record["body"]))
