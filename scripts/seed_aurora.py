"""Seed Aurora (pgvector) from the baked demo corpus so the live demo runs on
the real backend. Run once, offline, with AWS creds + a migrated cluster:

    python -m scripts.seed_aurora --corpus api/data/demo_corpus.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict


def split_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    text = [r for r in records if r.get("modality") == "text"]
    figs = [r for r in records if r.get("modality") == "figure"]
    return text, figs


def main() -> None:
    p = argparse.ArgumentParser(prog="seed_aurora")
    p.add_argument("--corpus", default="api/data/demo_corpus.json")
    args = p.parse_args()
    from api.config import get_settings
    from api.embeddings import build_embedder
    from api.store_aurora import AuroraVectorStore

    s = get_settings()
    data = json.load(open(args.corpus, encoding="utf-8"))
    emb = build_embedder(s.embedder, s.bedrock_embedding_model, s.embedding_dim)
    store = AuroraVectorStore(s.aurora_cluster_arn, s.aurora_secret_arn,
                              s.aurora_database, emb, dim=s.embedding_dim,
                              region=s.aws_region)
    by_paper: dict[str, list[dict]] = defaultdict(list)
    for r in data["records"]:
        by_paper[r["paper_id"]].append(r)
    for paper_id, recs in by_paper.items():
        text, figs = split_records(recs)
        store.upsert_paper(paper_id, text, figs)
        print(f"  seeded {paper_id}: {len(text)} text, {len(figs)} figures")
    print(f"seeded {len(by_paper)} papers")


if __name__ == "__main__":
    main()
