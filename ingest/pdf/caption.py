"""Figure understanding. Default is local (echo the detected caption); an
optional Bedrock-vision impl enriches captions but is never the default so
local runs and CI stay cloud-free.
"""
from __future__ import annotations

from PIL import Image


class CaptionTextUnderstander:
    """Zero-cost default: the figure's own detected caption is the description."""

    def describe(self, crop: Image.Image, nearby_caption: str) -> str:
        return nearby_caption


class BedrockVisionUnderstander:
    """Richer captions via Bedrock Claude vision. Opt-in (needs AWS creds)."""

    def __init__(self, generator=None) -> None:
        if generator is None:
            from api.config import get_settings
            from api.generation import build_generator

            s = get_settings()
            generator = build_generator(
                "bedrock", s.bedrock_generation_model, s.aws_region)
        self._gen = generator

    def describe(self, crop: Image.Image, nearby_caption: str) -> str:
        import base64
        import io

        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        prompt = ("Describe this scientific figure in 1-2 sentences for retrieval. "
                  f"Detected caption: {nearby_caption!r}")
        # Reuses the generator's vision path; returns "" if it declines.
        return self._gen.describe_image(b64, prompt) or nearby_caption
