"""Answer generators.

Two implementations behind one interface:

- `ExtractiveGenerator` — deterministic, dependency-free. Stitches the top
  retrieved passage and figure caption into a grounded answer. The default, so
  the demo backend and tests need no model.
- `QwenVisionGenerator` — a local Hugging Face Qwen2.5-VL model that reasons over
  the retrieved text AND the actual figure images (fetched from each figure
  citation's `image_uri`). Heavy deps (torch/transformers), imported lazily and
  kept in requirements-ml.txt.

Both take the retrieved citations and return answer text; the citation list
(the grounding) is owned by the pipeline and unchanged by the generator. When a
generator can't ground an answer it returns the empty string, and the pipeline
turns that into a refusal.
"""

from __future__ import annotations

import io
import urllib.request
from typing import Protocol

from .schemas import Citation, Modality

_USER_AGENT = "central-dogma/0.1"

_SYSTEM = (
    "You are a scientific literature assistant. Answer the question using ONLY the "
    "provided sources: text passages and figure images with their captions. After "
    "each claim, cite its source inline in brackets — a figure by label ([Figure 3]) "
    "or a passage by its section ([Methods]). Do not use outside knowledge. If the "
    "sources do not support an answer, reply with exactly: NO_ANSWER."
)


class Generator(Protocol):
    def generate(self, question: str, citations: list[Citation]) -> str: ...


def _split(citations: list[Citation]) -> tuple[list[Citation], list[Citation]]:
    text = [c for c in citations if c.modality == Modality.TEXT]
    figures = [c for c in citations if c.modality == Modality.FIGURE]
    return text, figures


class ExtractiveGenerator:
    """Deterministic, no-model answer used by the demo backend and tests."""

    def generate(self, question: str, citations: list[Citation]) -> str:
        text, figures = _split(citations)
        parts: list[str] = []
        if text:
            parts.append(text[0].snippet)
        if figures:
            f = figures[0]
            parts.append(f"{f.figure_label or 'The figure'} supports this: {f.snippet}")
        return " ".join(parts)


def _fetch_image(url: str):
    """Fetch a figure image URL and return a PIL RGB image."""
    from PIL import Image  # lazy: only the vision path needs Pillow

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


class QwenVisionGenerator:
    """Local Qwen2.5-VL that reasons over retrieved text + figure images."""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-VL-3B-Instruct") -> None:
        # Lazy so the base image / demo backend never import torch/transformers.
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        # On managed networks, route TLS through the OS trust store for the CDN fetch.
        try:
            import truststore

            truststore.inject_into_ssl()
        except Exception:
            pass

        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_name, torch_dtype="auto", device_map="auto"
        )
        self._processor = AutoProcessor.from_pretrained(model_name)

    def _build_messages(self, question: str, citations: list[Citation]) -> tuple[list, list]:
        text, figures = _split(citations)
        content: list[dict] = []
        if text:
            passages = "\n\n".join(
                f"[Passage — {c.section or 'source'}]: {c.snippet}" for c in text
            )
            content.append({"type": "text", "text": "Text sources:\n" + passages})

        images = []
        for c in figures:
            if c.image_uri:
                try:
                    img = _fetch_image(c.image_uri)
                except Exception:
                    continue  # unreachable image: fall back to its caption text only
                images.append(img)
                content.append({"type": "text", "text": f"{c.figure_label or 'Figure'} caption: {c.snippet}"})
                content.append({"type": "image", "image": img})
            else:
                content.append({"type": "text", "text": f"{c.figure_label or 'Figure'} caption: {c.snippet}"})

        content.append({"type": "text", "text": f"Question: {question}"})
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": content},
        ]
        return messages, images

    def generate(self, question: str, citations: list[Citation]) -> str:
        messages, images = self._build_messages(question, citations)
        prompt = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(
            text=[prompt], images=images or None, padding=True, return_tensors="pt"
        ).to(self._model.device)
        generated = self._model.generate(**inputs, max_new_tokens=512)
        trimmed = generated[:, inputs.input_ids.shape[1] :]
        answer = self._processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()
        # The model emits NO_ANSWER when the sources don't support one -> refuse.
        return "" if answer.strip().upper().startswith("NO_ANSWER") else answer


def build_generator(kind: str, model_name: str) -> Generator:
    if kind == "extractive":
        return ExtractiveGenerator()
    if kind == "qwen-vision":
        return QwenVisionGenerator(model_name=model_name)
    raise ValueError(f"unknown generator kind: {kind!r}")
