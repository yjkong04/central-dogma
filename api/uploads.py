"""Request-side upload helpers: reserve a durable cap slot, create a batch, and
hand back a presigned S3 POST (size-bounded at the edge so oversized uploads are
rejected before they cost anything). Status reads shape read_batch into the API
response. S3 access goes through _s3() so tests can fake it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import boto3

from . import status_store
from .config import get_settings

_s3_client = None


class UploadCapReached(Exception):
    pass


class BatchNotFound(Exception):
    pass


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=get_settings().aws_region)
    return _s3_client


def create_batch(filename: str, kind: str, *, now: datetime) -> dict:
    settings = get_settings()
    day = now.strftime("%Y-%m-%d")
    ttl_epoch = int((now + timedelta(days=2)).timestamp())
    # Cap counts upload REQUESTS, not stored objects — the slot is consumed here
    # before the client is guaranteed to POST the object (a benign over-count for
    # an anonymous-demo guardrail; 3b must not assume the counter equals stored batches).
    if not status_store.reserve_upload_slot(day, settings.upload_daily_cap, ttl_epoch):
        raise UploadCapReached("daily upload limit reached — try again tomorrow")

    batch_id = uuid4().hex
    status_store.put_batch(batch_id, created_at=now.isoformat())

    ext = "pdf" if kind == "pdf" else "zip"
    key = f"uploads/{batch_id}.{ext}"
    max_mb = settings.max_pdf_mb if kind == "pdf" else settings.max_zip_mb
    post = _s3().generate_presigned_post(
        Bucket=settings.uploads_bucket,
        Key=key,
        Conditions=[["content-length-range", 1, max_mb * 1_048_576]],
        ExpiresIn=settings.upload_url_ttl_s,
    )
    return {"batch_id": batch_id, "upload": {"url": post["url"], "fields": post["fields"]}}


def get_batch(batch_id: str) -> dict:
    data = status_store.read_batch(batch_id)
    if data is None:
        raise BatchNotFound(batch_id)
    batch = data["batch"]
    papers = [
        {"paper_id": p["paper_id"], "filename": p.get("filename", ""),
         "state": p.get("state", "pending"), "error": p.get("error")}
        for p in data["papers"]
    ]
    return {
        "batch_id": batch["batch_id"],
        "state": batch.get("state", "pending"),
        "total": int(batch.get("total", 0)),
        "done": int(batch.get("done", 0)),
        "failed": int(batch.get("failed", 0)),
        "papers": papers,
    }
