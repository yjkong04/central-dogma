"""CLI: python -m ingest.pdf <file.pdf> [--model layout.pt]

Prints sections + figures. Requires the ingest extras (requirements-ingest.txt)
and a layout checkpoint; uses docTR for OCR by default.
"""
from __future__ import annotations

import argparse

from .layout import YoloLayoutDetector
from .parse import parse_pdf


def main() -> None:
    ap = argparse.ArgumentParser(prog="ingest.pdf")
    ap.add_argument("pdf")
    ap.add_argument("--model", required=True, help="path to a YOLO/DETR layout checkpoint")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()
    paper = parse_pdf(args.pdf, layout=YoloLayoutDetector(args.model), dpi=args.dpi)
    print(f"paper_id={paper.paper_id} title={paper.title!r}")
    print(f"sections={len(paper.sections)} figures={len(paper.figures)}")
    for s in paper.sections:
        print(f"  [{s.title}] {s.text[:80]}...")
    for f in paper.figures:
        print(f"  <{f.label}> {f.caption[:80]} ({len(f.image_bytes or b'')} bytes)")


if __name__ == "__main__":
    main()
