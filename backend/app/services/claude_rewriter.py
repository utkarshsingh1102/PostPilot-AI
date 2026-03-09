"""
Claude-powered LinkedIn post rewriter.

Calls the Anthropic API to:
  - Rewrite a scraped post for clarity, engagement, and LinkedIn readability.
  - Generate an attention-grabbing hook.
  - Suggest relevant hashtags.

Returns a structured dict that maps directly to ProcessedPost fields.
"""

import json
import logging
from typing import Optional
import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are an expert LinkedIn content strategist and copywriter.
Your task is to rewrite LinkedIn posts to maximize engagement, clarity, and professional appeal.

Guidelines:
- Maintain the original meaning and key message.
- Use short paragraphs (1-3 sentences each) with line breaks between them.
- Add relevant emojis sparingly to improve scannability.
- Write in an authentic, conversational yet professional tone.
- Open with a strong hook that makes readers want to read more.
- End with a clear call-to-action or thought-provoking question.

You MUST respond with a valid JSON object matching this exact schema:
{
  "rewritten_post": "<full rewritten post text>",
  "hooks": "<1-2 sentence attention-grabbing opening line>",
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}

Return ONLY the JSON object. No markdown fences, no extra explanation."""


USER_PROMPT_TEMPLATE = """Please rewrite the following LinkedIn post:

---
{post_text}
---

Remember: respond ONLY with the JSON object."""


async def rewrite_post(post_text: str) -> dict:
    """
    Rewrite a LinkedIn post using Claude.

    Args:
        post_text: The raw scraped post text.

    Returns:
        dict with keys: rewritten_post, hooks, hashtags
    """
    client = _get_client()

    prompt = USER_PROMPT_TEMPLATE.format(post_text=post_text.strip())

    logger.info("Sending post to Claude for rewriting (length=%d chars).", len(post_text))

    try:
        message = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            system=SYSTEM_PROMPT,
        )

        raw_content = message.content[0].text.strip()
        logger.debug("Claude raw response: %s", raw_content[:300])

        # Strip accidental markdown fences if present
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
            raw_content = raw_content.strip()

        result = json.loads(raw_content)

        # Validate required keys
        required = {"rewritten_post", "hooks", "hashtags"}
        missing = required - set(result.keys())
        if missing:
            raise ValueError(f"Claude response missing keys: {missing}")

        # Ensure hashtags is a list
        if isinstance(result["hashtags"], str):
            result["hashtags"] = [tag.strip() for tag in result["hashtags"].split(",")]

        logger.info("Post rewritten successfully via Claude.")
        return result

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude JSON response: %s | raw: %s", exc, raw_content[:500])
        raise
    except Exception as exc:
        logger.error("Claude rewriting failed: %s", exc)
        raise


def build_copy_ready_text(rewritten_post: str, hashtags: list[str]) -> str:
    """Combine rewritten post and hashtags into a single copy-paste ready string."""
    tags_line = " ".join(hashtags) if hashtags else ""
    parts = [rewritten_post.strip()]
    if tags_line:
        parts.append("\n" + tags_line)
    return "\n".join(parts)
