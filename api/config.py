"""Runtime configuration, loaded from environment / .env.

Week 1 runs entirely off the in-memory demo store, so nothing here is
required. The database and model fields are wired up by later milestones
(Week 2: pgvector; Week 3: local Qwen2.5-VL vision generation).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CENTRALDOGMA_", extra="ignore")

    # "demo" (in-memory, no deps) or "pgvector" (real corpus).
    store_backend: str = "demo"

    database_url: str = "postgresql://centraldogma:centraldogma@localhost:5432/centraldogma"

    # Embeddings. "sentence-transformer" (local HF, production) or "hashing"
    # (deterministic, dependency-light, for tests/CI). Keep embedding_dim in sync
    # with the model AND db/schema.sql.
    embedder: str = "sentence-transformer"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Answer generation. "extractive" (no model, default so the demo/tests stay
    # light) or "qwen-vision" (local Qwen2.5-VL reasoning over figure images).
    generator: str = "extractive"
    vision_model: str = "Qwen/Qwen2.5-VL-3B-Instruct"

    # Context assembly (Week 4). Retrieve candidate_multiplier x top_k candidates,
    # then diversify/budget down so one question's context can span sections.
    retrieval_candidate_multiplier: int = 3
    context_char_budget: int = 4000
    per_section_cap: int = 2
    # Refuse when the best retrieval score is below this (0.0 = disabled; scale
    # depends on the embedder, so tune per embedding model).
    min_relevance_score: float = 0.0

    # AWS live demo (Bedrock via IAM; no keys). See docs/superpowers/specs/2026-09-05-live-demo-aws-design.md
    aws_region: str = "us-east-1"
    bedrock_generation_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"
    demo_corpus_path: str = "api/data/demo_corpus.json"
    allowed_origins: str = "*"  # comma-separated CORS origins for the public demo
    demo_daily_cap: int = 500   # best-effort per-container /ask cap

    # Aurora Serverless v2 + pgvector via the RDS Data API (Week 2 serverless variant).
    aurora_cluster_arn: str = ""
    aurora_secret_arn: str = ""
    aurora_database: str = "centraldogma"

    # Async ingestion (SP3). Uploads land in uploads_bucket via presigned POST;
    # batch/paper status + the durable daily cap live in DynamoDB.
    uploads_bucket: str = ""
    batches_table: str = "centraldogma-batches"
    papers_table: str = "centraldogma-papers"
    figures_bucket: str = ""
    figures_base_url: str = ""  # CloudFront/S3 base for stored figure crops (3b)
    max_zip_mb: int = 25
    max_pdfs_per_zip: int = 20   # enforced by 3b's dispatcher; defined here so it inherits
    max_pdf_mb: int = 20
    upload_daily_cap: int = 50
    upload_url_ttl_s: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
