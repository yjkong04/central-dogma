"""Build the baked-in demo corpus JSON (real PMC papers, pre-embedded).

Run ONCE, offline, with AWS creds (Titan embeddings via Bedrock):

    CENTRALDOGMA_EMBEDDER=bedrock CENTRALDOGMA_EMBEDDING_DIM=1024 \
      python -m scripts.build_demo_corpus --out api/data/demo_corpus.json

Commit the resulting JSON. Retrieval at runtime embeds the query with the
same embedder, so corpus and query must share the embedder + dim.
"""

from __future__ import annotations

import argparse
import json
import os

from ingest.chunk import chunk_paper
from ingest.figures import attach_figure_image_urls
from ingest.net import enable_os_trust_store
from ingest.pmc import fetch_and_parse

# Curated open-access PMC papers that demo well (biomedical, figure-rich).
# PLACEHOLDER LIST -- this must be reviewed and filled with a real, verified
# set of ~20 PMCIDs during deploy prep (see Task 10's runbook). Confirm each
# resolves (fetch_and_parse succeeds, has a non-trivial chunk count) before
# committing the real corpus; swap out any that 404 or are figure/text-thin.
PMCIDS = [
    "PMC13403225", "PMC13402739",
    # ... ~20 total; the implementer fills a reviewed list and prints per-paper
    # chunk counts so a thin/blocked paper can be swapped.
]


def records_from_paper(paper, chunks) -> list[dict]:
    """Map ingest Chunks to JSON records.

    Mirrors ingest/index.py:write_paper's field extraction: the real
    ingest.chunk.Chunk dataclass carries `chunk_id` (not `source_id`) and
    `content` (not `text`) for both text chunks and figures alike --
    chunk_paper() already folds a figure's caption (or label, or "figure")
    into `content`, so `text` here is uniformly "the chunk's content".
    """
    out: list[dict] = []
    for ch in chunks:
        out.append({
            "paper_id": paper.paper_id,
            "source_id": ch.chunk_id,
            "modality": ch.modality,            # "text" | "figure"
            "section": ch.section,
            "figure_label": getattr(ch, "figure_label", None),
            "image_uri": getattr(ch, "image_uri", None),
            "text": ch.content,                  # chunk content or figure caption
        })
    return out


def build(pmcids: list[str], embedder, out_path: str) -> None:
    enable_os_trust_store()
    records: list[dict] = []
    for pmcid in pmcids:
        paper = fetch_and_parse(pmcid)
        try:
            attach_figure_image_urls(paper)
        except Exception as e:
            print(f"  {pmcid}: figure images unresolved ({type(e).__name__})")
        recs = records_from_paper(paper, chunk_paper(paper))
        vecs = embedder.embed([r["text"] for r in recs]) if recs else []
        for r, v in zip(recs, vecs):
            r["embedding"] = [float(x) for x in v]
        records.extend(recs)
        print(f"  {pmcid}: {len(recs)} records")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"embedding_model": getattr(embedder, "model_id", "bedrock"),
                   "dim": embedder.dim, "records": records}, fh)
    print(f"wrote {len(records)} records -> {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(prog="build_demo_corpus")
    p.add_argument("--out", default="api/data/demo_corpus.json")
    args = p.parse_args()
    from api.config import get_settings
    from api.embeddings import build_embedder

    s = get_settings()
    build(PMCIDS, build_embedder(s.embedder, s.embedding_model, s.embedding_dim), args.out)


if __name__ == "__main__":
    main()
