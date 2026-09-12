"""Retrieval store abstraction + an in-memory demo implementation.

The store is the seam between retrieval and the rest of the app. Week 1 ships
`DemoStore` so the API returns a real, cited response shape with zero setup.
Week 2 adds a `PgVectorStore` behind the same `Store` protocol and the app
switches on `settings.store_backend` — no changes to the API layer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import numpy as np

from .schemas import Modality

if TYPE_CHECKING:
    from .embeddings import Embedder


@dataclass
class Record:
    """One retrievable unit: a text chunk or a figure."""

    paper_id: str
    source_id: str
    modality: Modality
    text: str  # chunk text, or figure caption
    section: str | None = None
    figure_label: str | None = None
    image_uri: str | None = None  # populated for figures from Week 3


@dataclass
class ScoredRecord:
    record: Record
    score: float


class Store(Protocol):
    def search_text(self, query: str, k: int) -> list[ScoredRecord]: ...
    def search_figures(self, query: str, k: int) -> list[ScoredRecord]: ...
    @property
    def name(self) -> str: ...


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def _overlap_score(query: str, text: str) -> float:
    """Cheap lexical overlap. Stand-in for dense similarity until Week 2.

    Real embeddings replace this; the interface (query, text) -> score stays.
    """
    q = set(_tokenize(query))
    if not q:
        return 0.0
    t = _tokenize(text)
    if not t:
        return 0.0
    hits = sum(1 for tok in t if tok in q)
    return hits / (len(t) ** 0.5)  # length-normalized so long chunks don't dominate


@dataclass
class DemoStore:
    """A tiny hand-built corpus so the API works end to end with no DB.

    The content is synthetic and generic on purpose — it exists to exercise
    text + figure retrieval and the citation shape, not to be real science.
    """

    records: list[Record] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "demo"

    def __post_init__(self) -> None:
        if not self.records:
            self.records = _demo_records()

    def _search(self, query: str, k: int, modality: Modality) -> list[ScoredRecord]:
        scored = [
            ScoredRecord(r, _overlap_score(query, r.text))
            for r in self.records
            if r.modality == modality
        ]
        scored = [s for s in scored if s.score > 0]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:k]

    def search_text(self, query: str, k: int) -> list[ScoredRecord]:
        return self._search(query, k, Modality.TEXT)

    def search_figures(self, query: str, k: int) -> list[ScoredRecord]:
        return self._search(query, k, Modality.FIGURE)


class PgVectorStore:
    """Dense retrieval over Postgres + pgvector.

    Embeds the query at request time with the same embedder used at ingestion,
    then cosine-ranks text chunks and figure captions with the `<=>` operator.
    Score is 1 - cosine_distance, so higher is more similar (matching DemoStore).
    """

    def __init__(self, dsn: str, embedder: "Embedder") -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self._embedder = embedder
        self._conn = psycopg.connect(dsn, autocommit=True)
        register_vector(self._conn)

    @property
    def name(self) -> str:
        return "pgvector"

    def _embed_query(self, query: str):
        return self._embedder.embed([query])[0]

    def search_text(self, query: str, k: int) -> list[ScoredRecord]:
        if k <= 0:
            return []
        vec = self._embed_query(query)
        rows = self._conn.execute(
            """
            SELECT chunk_id, paper_id, section, content,
                   1 - (embedding <=> %s) AS score
            FROM text_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (vec, vec, k),
        ).fetchall()
        return [
            ScoredRecord(
                Record(
                    paper_id=paper_id,
                    source_id=chunk_id,
                    modality=Modality.TEXT,
                    text=content,
                    section=section,
                ),
                float(score),
            )
            for chunk_id, paper_id, section, content, score in rows
        ]

    def search_figures(self, query: str, k: int) -> list[ScoredRecord]:
        if k <= 0:
            return []
        vec = self._embed_query(query)
        rows = self._conn.execute(
            """
            SELECT figure_id, paper_id, section, figure_label, caption, image_uri,
                   1 - (caption_embedding <=> %s) AS score
            FROM figures
            WHERE caption_embedding IS NOT NULL
            ORDER BY caption_embedding <=> %s
            LIMIT %s
            """,
            (vec, vec, k),
        ).fetchall()
        return [
            ScoredRecord(
                Record(
                    paper_id=paper_id,
                    source_id=figure_id,
                    modality=Modality.FIGURE,
                    text=caption,
                    section=section,
                    figure_label=figure_label,
                    image_uri=image_uri,
                ),
                float(score),
            )
            for figure_id, paper_id, section, figure_label, caption, image_uri, score in rows
        ]


class FileVectorStore:
    """Dense retrieval over a pre-embedded JSON corpus, held in memory.

    Real papers, no database. The query is embedded at request time with the
    injected embedder; ranking is a dot product over L2-normalized vectors
    (== cosine), matching PgVectorStore's score semantics.
    """

    def __init__(self, records: list[Record], matrix: np.ndarray, embedder: "Embedder") -> None:
        self._records = records
        self._matrix = matrix  # (N, dim), L2-normalized
        self._embedder = embedder

    @property
    def name(self) -> str:
        return "file"

    @classmethod
    def from_file(cls, path: str, embedder: "Embedder") -> "FileVectorStore":
        from .embeddings import _l2_normalize

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        records: list[Record] = []
        vecs: list[list[float]] = []
        for r in data["records"]:
            records.append(
                Record(
                    paper_id=r["paper_id"],
                    source_id=r["source_id"],
                    modality=Modality(r["modality"]),
                    text=r["text"],
                    section=r.get("section"),
                    figure_label=r.get("figure_label"),
                    image_uri=r.get("image_uri"),
                )
            )
            vecs.append(r["embedding"])
        matrix = (
            _l2_normalize(np.asarray(vecs, dtype=np.float32))
            if records
            else np.zeros((0, int(data["dim"])), dtype=np.float32)
        )
        if records and matrix.shape[1] != embedder.dim:
            raise ValueError(
                f"corpus embedding dim {matrix.shape[1]} != embedder dim {embedder.dim}"
            )
        return cls(records, matrix, embedder)

    def _search(self, query: str, k: int, modality: Modality) -> list[ScoredRecord]:
        if k <= 0 or not self._records:
            return []
        q = self._embedder.embed([query])[0]
        scores = self._matrix @ q
        order = np.argsort(-scores)
        hits: list[ScoredRecord] = []
        for i in order:
            if self._records[i].modality == modality:
                hits.append(ScoredRecord(self._records[i], float(scores[i])))
                if len(hits) == k:
                    break
        return hits

    def search_text(self, query: str, k: int) -> list[ScoredRecord]:
        return self._search(query, k, Modality.TEXT)

    def search_figures(self, query: str, k: int) -> list[ScoredRecord]:
        return self._search(query, k, Modality.FIGURE)


def _demo_records() -> list[Record]:
    pid = "DEMO-0001"
    return [
        Record(
            paper_id=pid,
            source_id=f"{pid}:c1",
            modality=Modality.TEXT,
            section="Methods",
            text=(
                "Samples were treated with the compound across a dose series and "
                "response was measured after 48 hours using a standard viability assay. "
                "Each condition was run in triplicate."
            ),
        ),
        Record(
            paper_id=pid,
            source_id=f"{pid}:c2",
            modality=Modality.TEXT,
            section="Results",
            text=(
                "Response increased monotonically with dose up to the mid range and "
                "then plateaued, consistent with a saturating dose-response relationship. "
                "The effect was reproducible across replicates."
            ),
        ),
        Record(
            paper_id=pid,
            source_id=f"{pid}:c3",
            modality=Modality.TEXT,
            section="Discussion",
            text=(
                "The plateau at higher doses suggests target saturation rather than "
                "toxicity, since viability of control samples was unchanged."
            ),
        ),
        Record(
            paper_id=pid,
            source_id=f"{pid}:fig3",
            modality=Modality.FIGURE,
            section="Results",
            figure_label="Figure 3",
            image_uri="demo://figure-3",
            text=(
                "Figure 3. Dose-response curve. Measured response (y-axis) versus dose "
                "(x-axis, log scale). Response rises with dose then plateaus; error bars "
                "show standard deviation across triplicates."
            ),
        ),
    ]
