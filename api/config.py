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


@lru_cache
def get_settings() -> Settings:
    return Settings()
