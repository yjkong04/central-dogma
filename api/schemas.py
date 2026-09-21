"""Request/response models shared across the API.

These define the contract the frontend and eval harness code against, so they
are intentionally stable even while the retrieval and generation internals
change milestone to milestone.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Modality(str, Enum):
    TEXT = "text"
    FIGURE = "figure"


class Citation(BaseModel):
    """A pointer back to the exact source a claim came from.

    Every claim in an answer must carry at least one of these. A text citation
    resolves to a chunk within a section; a figure citation resolves to a
    specific figure by id. The frontend uses these to highlight the source.
    """

    modality: Modality
    paper_id: str = Field(..., description="Corpus id of the source paper, e.g. a PMC id")
    source_id: str = Field(..., description="Chunk id (text) or figure id (figure)")
    section: str | None = Field(None, description="Section the passage/figure lives in")
    figure_label: str | None = Field(None, description="Human label, e.g. 'Figure 3'")
    image_uri: str | None = Field(None, description="URL of the figure image, for figure citations")
    snippet: str = Field(..., description="The retrieved text, or the figure caption")
    score: float = Field(..., description="Retrieval relevance score for this source")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Natural-language question over the corpus")
    top_k_text: int = Field(4, ge=0, le=20)
    top_k_figures: int = Field(2, ge=0, le=10)
    paper_id: str | None = Field(default=None, description="Restrict retrieval to one paper (optional)")


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    # "answered" = grounded answer produced; "refused" = corpus didn't support one.
    status: Literal["answered", "refused"]
    # Which store backed this response, so callers know if it's the demo or real corpus.
    backend: str
    # Retrieval-strength proxy (top citation score); None when refused.
    confidence: float | None = None
    # Distinct sections the answer draws on — a multi-hop coverage signal.
    sections_covered: int = 0


class UploadRequest(BaseModel):
    filename: str
    kind: Literal["zip", "pdf"] = "zip"


class PresignedPost(BaseModel):
    url: str
    fields: dict[str, str]


class UploadResponse(BaseModel):
    batch_id: str
    upload: PresignedPost


class PaperState(BaseModel):
    paper_id: str
    filename: str
    state: str
    error: str | None = None


class BatchStatusResponse(BaseModel):
    batch_id: str
    state: str
    total: int
    done: int
    failed: int
    papers: list[PaperState]
