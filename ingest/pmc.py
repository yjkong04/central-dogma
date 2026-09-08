"""Fetch and parse open-access papers from PubMed Central.

Uses NCBI E-utilities: esearch to find open-access PMC articles, efetch to pull
each article's JATS XML (full text + figure captions). Only the OA subset
returns full text via efetch, so we filter on `open access[filter]`.

Stdlib only (urllib + ElementTree) so ingestion has no heavy dependencies.
NCBI asks for <= 3 requests/second without an API key; callers should stay
polite. See https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_USER_AGENT = "central-dogma/0.1 (https://github.com/yjkong04/multimodal-scientific-rag)"


@dataclass
class Figure:
    label: str | None  # e.g. "Figure 3"
    caption: str
    fig_id: str | None = None  # JATS xml id, useful to resolve the image file later
    graphic_href: str | None = None  # <graphic> filename; resolves to a public image URL
    image_uri: str | None = None  # CDN image URL, filled in by ingest.figures


@dataclass
class Section:
    title: str | None
    text: str


@dataclass
class ParsedPaper:
    paper_id: str  # PMCID, e.g. "PMC13402729"
    title: str | None
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def search_oa_pmcids(query: str, limit: int = 10) -> list[str]:
    """Return PMCIDs of open-access articles matching `query`."""
    term = f"({query}) AND open access[filter]"
    params = urllib.parse.urlencode(
        {"db": "pmc", "term": term, "retmax": limit, "retmode": "json"}
    )
    import json

    data = json.loads(_get(f"{EUTILS}/esearch.fcgi?{params}"))
    return [f"PMC{uid}" for uid in data["esearchresult"]["idlist"]]


def _local(tag: str) -> str:
    """Strip an XML namespace so we can match on the bare tag name."""
    return tag.rsplit("}", 1)[-1]


def _text(el: ET.Element | None) -> str:
    """Flatten an element's text content, including nested tags, to a string."""
    if el is None:
        return ""
    parts = [el.text or ""]
    for child in el:
        parts.append(_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _norm(s: str) -> str:
    return " ".join(s.split()).strip()


def _href(el: ET.Element) -> str | None:
    """The href of an element, from its xlink-namespaced (or bare) `href` attr."""
    for key, val in el.attrib.items():
        if _local(key) == "href":
            return val
    return None


def _graphic_href(fig_el: ET.Element) -> str | None:
    """The image filename a <fig> displays, from its <graphic> element.

    Prefers a <graphic> that is a direct child of the <fig> (the figure's own
    image), falling back to a descendant <graphic>. Deliberately ignores
    <inline-graphic> (inline icons/formulae, e.g. inside the caption), which is
    not the figure's display image.
    """
    for c in fig_el:  # direct children first
        if _local(c.tag) == "graphic":
            href = _href(c)
            if href:
                return href
    for c in fig_el.iter():  # then any descendant <graphic>
        if _local(c.tag) == "graphic":
            href = _href(c)
            if href:
                return href
    return None


def fetch_jats(pmcid: str) -> bytes:
    """Fetch one article's JATS XML by PMCID (with or without the 'PMC' prefix)."""
    uid = pmcid.removeprefix("PMC")
    params = urllib.parse.urlencode({"db": "pmc", "id": uid, "retmode": "xml"})
    return _get(f"{EUTILS}/efetch.fcgi?{params}")


def parse_article(xml_bytes: bytes, paper_id: str) -> ParsedPaper:
    """Parse JATS XML into a title, flat section list, and figure captions.

    Figures are collected wherever they appear (they are often nested inside
    sections), each keeping its label and caption so a citation can point at it.
    """
    root = ET.fromstring(xml_bytes)

    title = None
    figures: list[Figure] = []
    sections: list[Section] = []

    for el in root.iter():
        tag = _local(el.tag)
        if tag == "article-title" and title is None:
            title = _norm(_text(el))
        elif tag == "fig":
            label_el = next((c for c in el if _local(c.tag) == "label"), None)
            caption_el = next((c for c in el if _local(c.tag) == "caption"), None)
            caption = _norm(_text(caption_el)) if caption_el is not None else ""
            graphic_href = _graphic_href(el)
            # Keep a figure if it has a caption OR an image: a caption-less figure
            # still carries an image the vision step can reason over.
            if caption or graphic_href:
                figures.append(
                    Figure(
                        label=_norm(_text(label_el)) if label_el is not None else None,
                        caption=caption,
                        fig_id=el.get("id"),
                        graphic_href=graphic_href,
                    )
                )

    # Sections: top-level <sec> in <body>. Take the section title + its direct
    # paragraphs (nested subsections are flattened into their own entries by the
    # same pass, since we iterate every <sec>).
    body = next((el for el in root.iter() if _local(el.tag) == "body"), None)
    if body is not None:
        for sec in (el for el in body.iter() if _local(el.tag) == "sec"):
            sec_title = next((c for c in sec if _local(c.tag) == "title"), None)
            paras = [_text(c) for c in sec if _local(c.tag) == "p"]
            text = _norm(" ".join(paras))
            if text:
                sections.append(
                    Section(title=_norm(_text(sec_title)) if sec_title is not None else None, text=text)
                )

    return ParsedPaper(paper_id=paper_id, title=title, sections=sections, figures=figures)


def fetch_and_parse(pmcid: str, polite_delay: float = 0.4) -> ParsedPaper:
    paper = parse_article(fetch_jats(pmcid), paper_id=pmcid)
    time.sleep(polite_delay)  # stay under NCBI's rate limit
    return paper
