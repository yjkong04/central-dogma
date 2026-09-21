"""Shared types + protocols for the PDF ingestion pipeline.

Real ML models (OCR, layout) sit behind these protocols so pure logic is
tested with fakes and heavy adapters are swapped in at the edges.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from PIL import Image

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1 in page pixels


class PdfIngestError(Exception):
    """Raised when a PDF cannot be rendered or parsed."""


@dataclass
class TextBlock:
    text: str
    bbox: BBox
    page: int


@dataclass
class Page:
    index: int
    image: Image.Image
    native_text: list[TextBlock] = field(default_factory=list)  # empty if no text layer


@dataclass
class Region:
    kind: str  # "title" | "text" | "list" | "figure" | "table" | "caption"
    bbox: BBox
    page: int
    score: float = 1.0


@runtime_checkable
class Ocr(Protocol):
    def run(self, image: Image.Image, page: int) -> list[TextBlock]: ...


@runtime_checkable
class LayoutDetector(Protocol):
    def detect(self, image: Image.Image, page: int) -> list[Region]: ...


@runtime_checkable
class FigureUnderstander(Protocol):
    def describe(self, crop: Image.Image, nearby_caption: str) -> str: ...
