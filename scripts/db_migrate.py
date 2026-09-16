"""Create the pgvector schema in Aurora via the RDS Data API. Run once:

    python -m scripts.db_migrate
"""
from __future__ import annotations

DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    ("CREATE TABLE IF NOT EXISTS text_chunks ("
     "chunk_id text PRIMARY KEY, paper_id text NOT NULL, section text, "
     "content text NOT NULL, embedding vector(1024))"),
    ("CREATE TABLE IF NOT EXISTS figures ("
     "figure_id text PRIMARY KEY, paper_id text NOT NULL, section text, "
     "figure_label text, caption text NOT NULL, image_uri text, "
     "image_bytes bytea, caption_embedding vector(1024))"),
    "CREATE INDEX IF NOT EXISTS text_chunks_paper ON text_chunks (paper_id)",
    "CREATE INDEX IF NOT EXISTS figures_paper ON figures (paper_id)",
    ("CREATE INDEX IF NOT EXISTS text_chunks_hnsw ON text_chunks "
     "USING hnsw (embedding vector_cosine_ops)"),
    ("CREATE INDEX IF NOT EXISTS figures_hnsw ON figures "
     "USING hnsw (caption_embedding vector_cosine_ops)"),
]


def main() -> None:
    from api.config import get_settings
    from api.store_aurora import _client

    s = get_settings()
    rds = _client(s.aws_region)
    for stmt in DDL:
        rds.execute_statement(resourceArn=s.aurora_cluster_arn,
                              secretArn=s.aurora_secret_arn,
                              database=s.aurora_database, sql=stmt)
        print(f"ok: {stmt[:60]}...")
    print("migration complete")


if __name__ == "__main__":
    main()
