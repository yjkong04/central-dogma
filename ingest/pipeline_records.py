"""Pure join of SP1 chunks + embeddings into the record dicts SP2's
AuroraVectorStore.upsert_paper consumes. No AWS, no I/O — fully unit-testable.

3b's store_crops supplies crop_urls (fig_id -> stored crop URL); when a figure
is absent from that map we fall back to the chunk's existing image_uri (the PMC
CDN path). Both may be None.
"""

from __future__ import annotations

from typing import Sequence

from .chunk import Chunk
from .pmc import ParsedPaper


def build_records(
    paper: ParsedPaper,
    chunks: list[Chunk],
    embeddings: Sequence[Sequence[float]],
    crop_urls: dict[str, str] | None = None,
) -> tuple[list[dict], list[dict]]:
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks/embeddings length mismatch: {len(chunks)} != {len(embeddings)}"
        )
    crop_urls = crop_urls or {}
    text_records: list[dict] = []
    figure_records: list[dict] = []
    for chunk, embedding in zip(chunks, embeddings):
        if chunk.modality == "figure":
            image_uri = crop_urls.get(chunk.fig_id) or chunk.image_uri
            figure_records.append({
                "source_id": chunk.chunk_id,
                "section": chunk.section,
                "figure_label": chunk.figure_label,
                "content": chunk.content,
                "image_uri": image_uri,
                "embedding": embedding,
            })
        else:
            text_records.append({
                "source_id": chunk.chunk_id,
                "section": chunk.section,
                "content": chunk.content,
                "embedding": embedding,
            })
    return text_records, figure_records
