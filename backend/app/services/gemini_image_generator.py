"""
Gemini image generator service.

Given the locally-saved scraped image, uses Gemini's multimodal image generation
to produce a new image that closely mirrors the original — preserving faces,
expressions, composition, and professional tone.

If no scraped image is provided the function returns None immediately (no generation).

IMPORTANT: This service only GENERATES images locally and stores them.
It does NOT publish anything to LinkedIn or any other social platform.
"""

import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types as genai_types

from app.config import settings

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.GEMINI_API_KEY)
_IMAGES_DIR = Path(settings.GENERATED_IMAGES_DIR)


def _ensure_images_dir() -> Path:
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return _IMAGES_DIR


def _mime_type(path: Path) -> str:
    """Return MIME type for the image file, defaulting to image/jpeg."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "image/jpeg"


def _build_prompt(rewritten_post: str, variation_hint: Optional[str] = None) -> str:
    excerpt = rewritten_post.strip()[:350]
    variation_line = (
        f"STYLE DIRECTION for this version: {variation_hint}. "
        "Let this guide your creative choices for the environment, lighting, and colour palette.\n\n"
        if variation_hint else ""
    )
    return (
        "You are a creative visual artist generating a LinkedIn post image. "
        "A reference photo is provided. Your task:\n\n"
        "STRICT IDENTITY RULES — ABSOLUTE NON-NEGOTIABLE:\n"
        "1. DO NOT add any new person to the image who does not appear in the reference.\n"
        "2. DO NOT remove any existing person from the image.\n"
        "3. DO NOT alter the face, skin tone, facial structure, or features of any person.\n"
        "4. Preserve every person's identity exactly — they must be instantly "
        "recognisable as the same individuals from the reference photo.\n"
        "5. Maintain the same number of people and their relative positions unless the "
        "style direction below explicitly calls for a framing adjustment.\n\n"
        "CREATIVE FREEDOM — you have complete creative freedom over everything else: "
        "the background, environment, setting, lighting, colour palette, mood, and "
        "visual style. Reimagine the scene in a way that is visually striking, "
        "professional, and relevant to this post topic:\n\n"
        f"{excerpt}\n\n"
        f"{variation_line}"
        "Create something that would stop someone scrolling LinkedIn — bold, polished, "
        "and memorable — while keeping every person's face and identity perfectly intact.\n\n"
        "NO TEXT — no watermarks, logos, overlays, or captions.\n\n"
        "Output only the image."
    )


async def generate_image(
    rewritten_post: str,
    original_image_path: Optional[str],
    variation_hint: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a Gemini image based on the scraped reference image.

    Args:
        rewritten_post:      AI-rewritten post text (used for context in the prompt).
        original_image_path: Local filesystem path to the scraped image.
                             If None, returns None immediately — no image is generated.

    Returns:
        Relative file path of the saved generated image, or None on failure / no input.
    """
    if not original_image_path:
        logger.debug("No scraped image provided — skipping Gemini generation.")
        return None

    source_path = Path(original_image_path)
    if not source_path.exists():
        logger.warning("Scraped image not found on disk: %s — skipping.", original_image_path)
        return None

    images_dir = _ensure_images_dir()
    image_bytes = source_path.read_bytes()
    mime = _mime_type(source_path)
    prompt = _build_prompt(rewritten_post, variation_hint=variation_hint)

    logger.info(
        "Requesting Gemini image generation (reference=%s, %d bytes, mime=%s).",
        source_path.name, len(image_bytes), mime,
    )

    try:
        response = _client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=[
                genai_types.Part(
                    inline_data=genai_types.Blob(mime_type=mime, data=image_bytes)
                ),
                genai_types.Part(text=prompt),
            ],
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        image_out: Optional[bytes] = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_out = part.inline_data.data
                break

        if not image_out:
            logger.warning("Gemini returned no image data — falling back to scraped image.")
            return None

        filename = f"gemini_{uuid.uuid4().hex}.png"
        filepath = images_dir / filename
        filepath.write_bytes(image_out)

        relative_path = str(filepath)
        logger.info("Gemini generated image saved: %s", relative_path)
        return relative_path

    except Exception as exc:
        logger.error("Gemini image generation failed: %s", exc)
        return None          # non-fatal — caller decides what to do with None


def get_download_url(generated_image_path: Optional[str], base_url: str = "") -> Optional[str]:
    """Convert a local image path to the publicly served /images/<filename> URL."""
    if not generated_image_path:
        return None
    filename = Path(generated_image_path).name
    return f"{base_url}/images/{filename}"
