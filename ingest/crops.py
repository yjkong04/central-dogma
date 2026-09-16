"""Figure-crop storage + the fig_id normalization that makes PDF crops reach
the store.

parse_pdf produces figures with image_bytes but fig_id=None; chunk_paper keys a
figure chunk on fig_id and build_records joins crop URLs on it — so without a
stable id, PDF figures land caption-only with no image. ensure_fig_ids assigns
fig{i} so chunk_paper + store_crops + build_records all key consistently.

store_crops is pure key/URL logic over an injected S3 client (tests fake it).
The figures bucket + the CloudFront serving that resolves base_url are SP3b-ii;
this module only writes the object and builds the durable URL string.
"""

from __future__ import annotations

from .pmc import Figure, ParsedPaper


def ensure_fig_ids(paper: ParsedPaper) -> ParsedPaper:
    for i, fig in enumerate(paper.figures):
        if not fig.fig_id:
            fig.fig_id = f"fig{i}"
    return paper


def store_crops(paper_id: str, figures: list[Figure], s3, bucket: str,
                base_url: str) -> dict[str, str]:
    urls: dict[str, str] = {}
    for fig in figures:
        if not fig.image_bytes:
            continue
        key = f"figures/{paper_id}/{fig.fig_id}.png"
        s3.put_object(Bucket=bucket, Key=key, Body=fig.image_bytes,
                      ContentType="image/png")
        urls[fig.fig_id] = f"{base_url}/{key}"
    return urls
