"""pgvector integration test.

Skipped unless a database is reachable (so the default CI run without a DB
stays green). To run it:

    docker compose up -d db
    CENTRALDOGMA_TEST_DB=1 python -m pytest tests/test_pgvector.py

Seeds a couple of rows through the real write path with the deterministic
hashing embedder, queries via PgVectorStore, and cleans up after itself.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CENTRALDOGMA_TEST_DB") != "1",
    reason="set CENTRALDOGMA_TEST_DB=1 with a running pgvector DB to run",
)


@pytest.fixture
def store_and_conn():
    import psycopg

    from api.config import get_settings
    from api.embeddings import build_embedder
    from api.store import PgVectorStore
    from ingest.chunk import Chunk
    from ingest.index import write_paper
    from ingest.pmc import ParsedPaper

    s = get_settings()
    embedder = build_embedder("hashing", s.embedding_model, s.embedding_dim)
    conn = psycopg.connect(s.database_url, autocommit=True)

    paper = ParsedPaper(paper_id="TEST0001", title="Test paper", sections=[], figures=[])
    chunks = [
        Chunk("TEST0001:c0", "TEST0001", "text", "Methods", "dose response viability assay", ord=0),
        Chunk("TEST0001:c1", "TEST0001", "text", "Results", "response plateaued at high dose", ord=1),
        Chunk("TEST0001:fig0", "TEST0001", "figure", None, "dose response curve", figure_label="Figure 1", ord=2),
    ]
    write_paper(conn, paper, chunks, embedder)

    store = PgVectorStore(s.database_url, embedder)
    yield store

    conn.execute("DELETE FROM papers WHERE paper_id = %s", ("TEST0001",))
    conn.close()


def test_text_retrieval_returns_ranked_hits(store_and_conn):
    hits = store_and_conn.search_text("dose response viability assay", 2)
    assert hits, "expected at least one text hit"
    assert hits[0].record.source_id == "TEST0001:c0"  # exact match ranks first
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True), "hits must be score-descending"


def test_figure_retrieval_returns_figure(store_and_conn):
    figs = store_and_conn.search_figures("dose response curve", 1)
    assert figs and figs[0].record.figure_label == "Figure 1"
