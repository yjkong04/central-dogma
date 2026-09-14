"""Resolve the public image URL for each figure in a PMC article.

A figure's real image is served from an opaque CDN path
(`cdn.ncbi.nlm.nih.gov/pmc/blobs/<shard>/<pmcid>/<hash>/<file>`) whose shard and
hash are NOT derivable from the PMCID + filename -- so the URL cannot be
constructed, only discovered. We fetch the rendered article page once per paper,
extract the CDN image URLs, and match each figure's `<graphic>` filename to its
URL. The resolvable URL is stored in `figures.image_uri`: the viewer links to it
and the vision step fetches it on demand. (The raw-file OA `.tar.gz` packages are
FTP-only, so this HTML route is the reliable HTTPS path.)
"""

from __future__ import annotations

import re
from pathlib import Path

from .pmc import ParsedPaper, _get

_ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles"
_CDN_IMG = re.compile(
    r"https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^\"'\s]+?\.(?:jpg|jpeg|png|gif|webp|tif|tiff)",
    re.IGNORECASE,
)


def fetch_figure_image_urls(pmcid: str) -> dict[str, str]:
    """Return {image filename -> CDN URL} by scraping the article page.

    Keyed by both the full basename and the extension-less stem, so a figure
    whose `<graphic>` href drops the extension still matches.
    """
    html = _get(f"{_ARTICLE}/{pmcid}/").decode("utf-8", "replace")
    out: dict[str, str] = {}
    for url in _CDN_IMG.findall(html):
        name = url.rsplit("/", 1)[-1]
        out.setdefault(name, url)
        out.setdefault(Path(name).stem, url)
    return out


def attach_figure_image_urls(paper: ParsedPaper) -> int:
    """Set image_uri on each figure from the article's CDN images. Returns matches."""
    figs = [f for f in paper.figures if f.graphic_href]
    if not figs:
        return 0
    urls = fetch_figure_image_urls(paper.paper_id)
    matched = 0
    for fig in figs:
        name = fig.graphic_href
        url = urls.get(name) or urls.get(Path(name).stem)
        if url:
            fig.image_uri = url
            matched += 1
    return matched
