"""Aurora Serverless v2 + pgvector store via the RDS Data API (no VPC).

Reuses the text_chunks/figures schema the psycopg PgVectorStore queries, but
executes over boto3 rds-data so the query Lambda needs no VPC and keeps its
Bedrock egress. Query vectors are passed as cast string params (:qvec::vector).
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .schemas import Modality
from .store import Record, ScoredRecord

if TYPE_CHECKING:
    from .embeddings import Embedder


def _client(region: str | None = None):
    import boto3
    return boto3.client("rds-data", region_name=region)


def _vec_literal(vec) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


class AuroraVectorStore:
    def __init__(self, cluster_arn: str, secret_arn: str, database: str,
                 embedder: "Embedder", dim: int = 1024, region: str | None = None) -> None:
        self._cluster_arn = cluster_arn
        self._secret_arn = secret_arn
        self._database = database
        self._embedder = embedder
        self._dim = dim
        self._rds = _client(region)

    @property
    def name(self) -> str:
        return "aurora"

    def _execute(self, sql: str, params: list[dict]):
        resp = self._rds.execute_statement(
            resourceArn=self._cluster_arn, secretArn=self._secret_arn,
            database=self._database, sql=sql, parameters=params,
            formatRecordsAs="JSON")
        raw = resp.get("formattedRecords")
        return json.loads(raw) if raw else []

    def _filter_clause(self, paper_ids, params) -> str:
        names = []
        for i, pid in enumerate(paper_ids):
            n = f"pid{i}"
            names.append(f":{n}")
            params.append({"name": n, "value": {"stringValue": pid}})
        return f" AND paper_id IN ({', '.join(names)})"

    def _query_params(self, query: str, k: int):
        vec = self._embedder.embed([query])[0]
        return [
            {"name": "qvec", "value": {"stringValue": _vec_literal(vec)}},
            {"name": "k", "value": {"longValue": int(k)}},
        ]

    def search_text(self, query: str, k: int,
                    paper_ids: list[str] | None = None) -> list[ScoredRecord]:
        if k <= 0 or paper_ids == []:
            return []
        params = self._query_params(query, k)
        where = "embedding IS NOT NULL"
        if paper_ids:
            where += self._filter_clause(paper_ids, params)
        sql = (f"SELECT chunk_id, paper_id, section, content, "
               f"1 - (embedding <=> :qvec::vector) AS score "
               f"FROM text_chunks WHERE {where} "
               f"ORDER BY embedding <=> :qvec::vector LIMIT :k")
        rows = self._execute(sql, params)
        return [
            ScoredRecord(Record(paper_id=r["paper_id"], source_id=r["chunk_id"],
                                modality=Modality.TEXT, text=r["content"],
                                section=r.get("section")), float(r["score"]))
            for r in rows
        ]

    def _tx_args(self, tx):
        return dict(resourceArn=self._cluster_arn, secretArn=self._secret_arn,
                    database=self._database, transactionId=tx)

    def upsert_paper(self, paper_id: str, text_records: list[dict],
                     figure_records: list[dict]) -> None:
        tx = self._rds.begin_transaction(
            resourceArn=self._cluster_arn, secretArn=self._secret_arn,
            database=self._database)["transactionId"]
        try:
            for table in ("text_chunks", "figures"):
                self._rds.execute_statement(
                    sql=f"DELETE FROM {table} WHERE paper_id = :pid",
                    parameters=[{"name": "pid", "value": {"stringValue": paper_id}}],
                    **self._tx_args(tx))
            if text_records:
                self._rds.batch_execute_statement(
                    sql=("INSERT INTO text_chunks "
                         "(chunk_id, paper_id, section, content, embedding) VALUES "
                         "(:chunk_id, :paper_id, :section, :content, :emb::vector)"),
                    parameterSets=[self._text_params(paper_id, r) for r in text_records],
                    **self._tx_args(tx))
            if figure_records:
                self._rds.batch_execute_statement(
                    sql=("INSERT INTO figures "
                         "(figure_id, paper_id, section, figure_label, caption, "
                         "image_uri, caption_embedding) VALUES "
                         "(:figure_id, :paper_id, :section, :figure_label, :caption, "
                         ":image_uri, :emb::vector)"),
                    parameterSets=[self._fig_params(paper_id, r) for r in figure_records],
                    **self._tx_args(tx))
            self._rds.commit_transaction(
                resourceArn=self._cluster_arn, secretArn=self._secret_arn,
                transactionId=tx)
        except Exception:
            self._rds.rollback_transaction(
                resourceArn=self._cluster_arn, secretArn=self._secret_arn,
                transactionId=tx)
            raise

    @staticmethod
    def _nullable(name, value):
        if value is None:
            return {"name": name, "value": {"isNull": True}}
        return {"name": name, "value": {"stringValue": str(value)}}

    def _text_params(self, paper_id, r):
        return [
            {"name": "chunk_id", "value": {"stringValue": r["source_id"]}},
            {"name": "paper_id", "value": {"stringValue": paper_id}},
            self._nullable("section", r.get("section")),
            {"name": "content", "value": {"stringValue": r.get("content", r.get("text", ""))}},
            {"name": "emb", "value": {"stringValue": _vec_literal(r["embedding"])}},
        ]

    def _fig_params(self, paper_id, r):
        return [
            {"name": "figure_id", "value": {"stringValue": r["source_id"]}},
            {"name": "paper_id", "value": {"stringValue": paper_id}},
            self._nullable("section", r.get("section")),
            self._nullable("figure_label", r.get("figure_label")),
            {"name": "caption", "value": {"stringValue": r.get("content", r.get("text", ""))}},
            self._nullable("image_uri", r.get("image_uri")),
            {"name": "emb", "value": {"stringValue": _vec_literal(r["embedding"])}},
        ]

    def search_figures(self, query: str, k: int,
                       paper_ids: list[str] | None = None) -> list[ScoredRecord]:
        if k <= 0 or paper_ids == []:
            return []
        params = self._query_params(query, k)
        where = "caption_embedding IS NOT NULL"
        if paper_ids:
            where += self._filter_clause(paper_ids, params)
        sql = (f"SELECT figure_id, paper_id, section, figure_label, caption, image_uri, "
               f"1 - (caption_embedding <=> :qvec::vector) AS score "
               f"FROM figures WHERE {where} "
               f"ORDER BY caption_embedding <=> :qvec::vector LIMIT :k")
        rows = self._execute(sql, params)
        return [
            ScoredRecord(Record(paper_id=r["paper_id"], source_id=r["figure_id"],
                                modality=Modality.FIGURE, text=r["caption"],
                                section=r.get("section"),
                                figure_label=r.get("figure_label"),
                                image_uri=r.get("image_uri")), float(r["score"]))
            for r in rows
        ]
