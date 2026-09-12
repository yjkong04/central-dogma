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

# Curated open-access PMC papers for the demo corpus — biomedical, figure-rich,
# recruiter-legible (oncology / immunotherapy / genomics / gene-editing / imaging).
# Selected 2026-09-11 from the PMC OA subset via `ingest.search_oa_pmcids`, keeping
# papers with >=3 figure chunks and >=20 text chunks (figure count in the comment).
# Each was verified to fetch_and_parse with the shown chunk counts; figure IMAGE
# resolution + embeddings happen at build time (a figure whose CDN image doesn't
# resolve degrades to caption-only). Swap any freely — this is just the demo set.
PMCIDS = [
    "PMC13559677",  # 10 fig — microplastics/nanoplastics prognostic gene signature
    "PMC13558434",  #  8 fig — reduced intra-frontal functional connectivity (fMRI)
    "PMC13559462",  #  8 fig — radiomics-habitat model for preoperative prediction
    "PMC13558819",  #  7 fig — generative chemistry platform for RNA-targeting molecules
    "PMC13559665",  #  7 fig — Porphyromonas gingivalis prognostic value & mechanisms
    "PMC13559783",  #  7 fig — comparative genomics: Streptomyces biosynthetic diversity
    "PMC13560538",  #  7 fig — in vivo genome editing of CNS SIV reservoirs (gene editing)
    "PMC13559641",  #  6 fig — m6A-related prognostic models, lung squamous carcinoma
    "PMC13559814",  #  6 fig — nonendoscopic screening for Barrett's esophagus
    "PMC13561219",  #  5 fig — therapeutic potential of Astragalin in Parkinson's disease
    "PMC13559560",  #  5 fig — HALP score predicts clinical outcomes in lung cancer
    "PMC13559591",  #  5 fig — familial adenomatous polyposis, in vitro & in vivo
    "PMC13559439",  #  4 fig — peripheral blood biomarkers in PD-1/PD-L1 immunotherapy
    "PMC13559656",  #  4 fig — lactate-induced epithelial-mesenchymal transition
    "PMC13560343",  #  4 fig — remodeling the tumor immune microenvironment (crosstalk)
    "PMC13559235",  #  4 fig — staging classification controversy in stage N3
    "PMC13559701",  #  3 fig — chronic liver disease treatment (MASLD focus)
    "PMC13559688",  #  3 fig — vision-language model for tactical combat casualty care
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
    emb_model = s.bedrock_embedding_model if s.embedder == "bedrock" else s.embedding_model
    build(PMCIDS, build_embedder(s.embedder, emb_model, s.embedding_dim), args.out)


if __name__ == "__main__":
    main()
