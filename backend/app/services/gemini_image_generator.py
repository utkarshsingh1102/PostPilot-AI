"""
Gemini image generator service.

Uses Google's Gemini image generation model to produce a visually similar image
based on the rewritten post content.  The generated image is saved to disk and
the local path / public URL is returned.

IMPORTANT: This service only GENERATES images locally and stores them.
It does NOT publish anything to LinkedIn or any other social platform.
"""

import base64
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from google.generativeai import types as genai_types

from app.config import settings

logger = logging.getLogger(__name__)

# Initialise the Gemini SDK once
genai.configure(api_key=settings.GEMINI_API_KEY)

# Local directory where generated images are saved
_IMAGES_DIR = Path(settings.GENERATED_IMAGES_DIR)


def _ensure_images_dir() -> Path:
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return _IMAGES_DIR


def _build_image_prompt(rewritten_post: str, original_image_url: Optional[str] = None) -> str:
    """
    Derive a descriptive image generation prompt from the rewritten post text.
    Keeps the prompt focused and concise for best results.
    """
    # Take the first ~400 chars as the thematic basis
    excerpt = rewritten_post.strip()[:400]

    prompt = (
        "Create a professional, high-quality LinkedIn-style social media image that visually "
        f"represents the following topic:\n\n{excerpt}\n\n"
        "Style guidelines:\n"
        "- Clean, modern design with clear focal point\n"
        "- Professional colour palette (blues, whites, greys or brand-appropriate tones)\n"
        "- No text overlaid on the image\n"
        "- Photorealistic or polished flat-design style\n"
        "- Suitable for a B2B professional audience"
    )
    return prompt


async def generate_image(rewritten_post: str, original_image_url: Optional[str] = None) -> Optional[str]:
    """
    Generate an image using Gemini and save it locally.

    Args:
        rewritten_post: The AI-rewritten post text used to craft the image prompt.
        original_image_url: The original LinkedIn image URL (used only for context, not fetched).

    Returns:
        Relative file path of the saved image (e.g. "generated_images/abc123.png"),
        or None if generation failed.
    """
    images_dir = _ensure_images_dir()
    prompt = _build_image_prompt(rewritten_post, original_image_url)

    logger.info("Requesting image from Gemini (prompt length=%d chars).", len(prompt))

    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)

        response = model.generate_content(
            contents=prompt,
            generation_config=genai_types.GenerationConfig(
                response_mime_type="image/png",
            ),
        )

        # Extract image bytes from response
        image_bytes: Optional[bytes] = None
        for part in response.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_bytes = base64.b64decode(part.inline_data.data)
                break

        if not image_bytes:
            # Some Gemini model versions return base64 text directly
            if response.text:
                try:
                    image_bytes = base64.b64decode(response.text)
                except Exception:
                    pass

        if not image_bytes:
            logger.warning("Gemini did not return image data in the response.")
            return None

        # Save to disk
        filename = f"{uuid.uuid4().hex}.png"
        filepath = images_dir / filename
        filepath.write_bytes(image_bytes)

        relative_path = str(filepath)
        logger.info("Generated image saved: %s", relative_path)
        return relative_path

    except Exception as exc:
        logger.error("Gemini image generation failed: %s", exc)
        return None


def get_download_url(generated_image_path: Optional[str], base_url: str = "") -> Optional[str]:
    """
    Convert a local image path to a publicly downloadable URL served by FastAPI.
    The /images/<filename> route must be mounted in main.py.
    """
    if not generated_image_path:
        return None
    filename = Path(generated_image_path).name
    return f"{base_url}/images/{filename}"
