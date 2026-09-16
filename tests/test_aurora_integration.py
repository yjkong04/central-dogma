import os

import pytest

pytestmark = pytest.mark.slow

REQUIRED = ("CENTRALDOGMA_AURORA_CLUSTER_ARN", "CENTRALDOGMA_AURORA_SECRET_ARN")


@pytest.mark.skipif(not all(os.environ.get(k) for k in REQUIRED),
                    reason="set Aurora cluster/secret env to run the live integration test")
def test_upsert_then_search_roundtrip():
    from api.config import get_settings
    from api.embeddings import build_embedder
    from api.store_aurora import AuroraVectorStore

    s = get_settings()
    emb = build_embedder(s.embedder, s.bedrock_embedding_model, s.embedding_dim)
    store = AuroraVectorStore(s.aurora_cluster_arn, s.aurora_secret_arn,
                              s.aurora_database, emb, dim=s.embedding_dim,
                              region=s.aws_region)
    store.upsert_paper("TEST",
        text_records=[{"source_id": "TEST:c0", "section": "S",
                       "text": "immunotherapy biomarkers",
                       "embedding": emb.embed(["immunotherapy biomarkers"])[0]}],
        figure_records=[])
    hits = store.search_text("immunotherapy biomarkers", k=3, paper_ids=["TEST"])
    assert hits and hits[0].record.paper_id == "TEST"
