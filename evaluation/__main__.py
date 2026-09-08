"""CLI: run the evaluation harness or the generator comparison sweep.

Examples
--------
Baseline eval on the demo corpus (no DB, no model)::

    CENTRALDOGMA_EMBEDDER=hashing python -m evaluation

Real corpus with the vision model, custom eval set::

    python -m evaluation --backend pgvector --generator qwen-vision \\
        --dataset evaluation/datasets/pmc_eval.jsonl

Comparison sweep across candidate generators::

    python -m evaluation --sweep --backend pgvector \\
        --dataset evaluation/datasets/pmc_eval.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys

from api.config import get_settings
from api.generation import Generator, build_generator
from api.store import DemoStore, PgVectorStore, Store

from . import report as report_mod
from . import sweep as sweep_mod
from .dataset import demo_cases, load_cases
from .harness import evaluate


def _build_store(backend: str) -> Store:
    if backend == "demo":
        return DemoStore()
    if backend == "pgvector":
        from api.embeddings import build_embedder

        settings = get_settings()
        embedder = build_embedder(
            settings.embedder, settings.embedding_model, settings.embedding_dim
        )
        return PgVectorStore(settings.database_url, embedder)
    raise SystemExit(f"unknown backend: {backend!r}")


def _build_generator(kind: str, vision_model: str) -> Generator:
    return build_generator(kind, vision_model)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    p = argparse.ArgumentParser(prog="python -m evaluation", description=__doc__)
    p.add_argument("--backend", default="demo", choices=["demo", "pgvector"])
    p.add_argument("--generator", default="extractive", choices=["extractive", "qwen-vision"])
    p.add_argument("--vision-model", default=settings.vision_model)
    p.add_argument("--dataset", default=None, help="JSONL eval set; defaults to the built-in demo set")
    p.add_argument("--k-text", type=int, default=4)
    p.add_argument("--k-figures", type=int, default=2)
    p.add_argument("--sweep", action="store_true", help="compare the candidate generators")
    p.add_argument("--json", dest="json_out", default=None, help="write the full report as JSON here")
    p.add_argument("--no-per-case", action="store_true", help="omit the per-case table")
    args = p.parse_args(argv)

    cases = load_cases(args.dataset) if args.dataset else demo_cases()
    store = _build_store(args.backend)

    if args.backend == "pgvector" and args.dataset is None:
        print(
            "warning: scoring the pgvector corpus against the demo gold set; "
            "pass --dataset for meaningful retrieval/citation numbers.",
            file=sys.stderr,
        )

    if args.sweep:
        reports = sweep_mod.run_sweep(
            store,
            sweep_mod.default_specs(),
            cases,
            k_text=args.k_text,
            k_figures=args.k_figures,
        )
        print(sweep_mod.comparison_markdown(reports))
        if args.json_out and reports:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump([report_mod.to_dict(r) for r in reports], fh, indent=2)
        return 0

    generator = _build_generator(args.generator, args.vision_model)
    rep = evaluate(
        store, generator, cases, k_text=args.k_text, k_figures=args.k_figures
    )
    print(report_mod.to_markdown(rep, per_case=not args.no_per_case))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report_mod.to_dict(rep), fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
