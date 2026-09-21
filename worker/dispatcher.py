"""S3 ObjectCreated -> unzip/validate -> fan each PDF onto SQS.

Light zip Lambda (no models). Parses the upload, writes each PDF to the retained
papers/ prefix, creates a pending paper item per PDF, records the batch total,
and enqueues one message per PDF for the SP3b-ii worker. On a validation error
the whole batch is marked failed and nothing is fanned out.
"""

from __future__ import annotations

import json
from urllib.parse import unquote_plus

import boto3

from api import status_store
from api.config import get_settings
from worker.plan_batch import PlanError, PlanLimits, plan_batch

_s3_client = None
_sqs_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=get_settings().aws_region)
    return _s3_client


def _sqs():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs", region_name=get_settings().aws_region)
    return _sqs_client


def _parse_key(key: str) -> tuple[str, str]:
    # uploads/{batch_id}.{zip|pdf}
    stem = key.split("/", 1)[1] if "/" in key else key
    batch_id, _, ext = stem.rpartition(".")
    return batch_id, ext.lower()


def _dispatch_one(bucket: str, key: str) -> None:
    settings = get_settings()
    batch_id, kind = _parse_key(key)
    data = _s3().get_object(Bucket=bucket, Key=key)["Body"].read()
    try:
        entries = plan_batch(
            data, kind,
            PlanLimits(settings.max_pdfs_per_zip, settings.max_pdf_mb),
        )
    except PlanError as exc:
        status_store.mark_batch_failed(batch_id, str(exc))
        return

    for i, entry in enumerate(entries):
        paper_key = f"papers/{batch_id}/{i}.pdf"
        paper_id = f"batch-{batch_id}-{i}"
        _s3().put_object(Bucket=bucket, Key=paper_key, Body=entry.data)
        status_store.put_paper(batch_id, paper_id, entry.filename)
        _sqs().send_message(
            QueueUrl=settings.uploads_queue_url,
            MessageBody=json.dumps({
                "batch_id": batch_id, "paper_key": paper_key,
                "paper_id": paper_id, "filename": entry.filename,
            }),
        )
    status_store.set_batch_total(batch_id, total=len(entries), state="running")


def handler(event, context) -> None:
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        _dispatch_one(bucket, key)
