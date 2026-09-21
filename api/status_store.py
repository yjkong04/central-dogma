"""DynamoDB-backed batch/paper status + a durable per-UTC-day upload cap.

All AWS access flows through _table(), which tests monkeypatch with an
in-memory fake (repo convention — no moto). The wall clock lives in the caller:
these functions take day / ttl_epoch / created_at as arguments so they stay
deterministic under test and correct under concurrent 3b workers (counter bumps
use an atomic ADD).
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from .config import get_settings

_resource = None


def _dynamo():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=get_settings().aws_region)
    return _resource


def _table(name: str):
    return _dynamo().Table(name)


def put_batch(batch_id: str, *, created_at: str, total: int = 0, state: str = "pending") -> None:
    _table(get_settings().batches_table).put_item(Item={
        "batch_id": batch_id, "total": total, "done": 0, "failed": 0,
        "state": state, "created_at": created_at,
    })


def put_paper(batch_id: str, paper_id: str, filename: str, state: str = "pending") -> None:
    _table(get_settings().papers_table).put_item(Item={
        "batch_id": batch_id, "paper_id": paper_id, "filename": filename, "state": state,
    })


def mark_paper(batch_id: str, paper_id: str, state: str, error: str | None = None) -> None:
    expr = "SET #s = :state"
    names = {"#s": "state"}
    vals = {":state": state}
    if error is not None:
        expr += ", #e = :error"
        names["#e"] = "error"
        vals[":error"] = error
    _table(get_settings().papers_table).update_item(
        Key={"batch_id": batch_id, "paper_id": paper_id},
        UpdateExpression=expr, ExpressionAttributeNames=names, ExpressionAttributeValues=vals,
    )


def bump_counters(batch_id: str, *, done: int = 0, failed: int = 0) -> None:
    _table(get_settings().batches_table).update_item(
        Key={"batch_id": batch_id},
        UpdateExpression="ADD done :d, failed :f",
        ExpressionAttributeValues={":d": done, ":f": failed},
    )


def _query_papers(batch_id: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key
    resp = _table(get_settings().papers_table).query(
        KeyConditionExpression=Key("batch_id").eq(batch_id)
    )
    return resp.get("Items", [])


def read_batch(batch_id: str) -> dict | None:
    batch = _table(get_settings().batches_table).get_item(Key={"batch_id": batch_id}).get("Item")
    if batch is None:
        return None
    return {"batch": batch, "papers": _query_papers(batch_id)}


def reserve_upload_slot(day: str, cap: int, ttl_epoch: int) -> bool:
    try:
        _table(get_settings().batches_table).update_item(
            Key={"batch_id": f"cap#{day}"},
            UpdateExpression="SET #t = if_not_exists(#t, :ttl) ADD #n :one",
            ConditionExpression="attribute_not_exists(#n) OR #n < :cap",
            ExpressionAttributeNames={"#n": "n", "#t": "ttl"},
            ExpressionAttributeValues={":one": 1, ":cap": cap, ":ttl": ttl_epoch},
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
