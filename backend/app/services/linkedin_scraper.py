"""
LinkedIn public post scraper using Playwright.

Design notes:
- Logs into LinkedIn once per session using credentials from .env.
- Navigates to the given source URL (company/profile posts feed).
- Extracts up to `max_posts` posts per run.
- Supports a `since_date` cutoff: scrolling stops as soon as a post older than
  the cutoff is encountered, making the initial bounded test run efficient.
- Returns structured dicts; duplicate filtering happens in the caller (cron job).
- DOES NOT publish, like, comment, or interact with LinkedIn in any way.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError as PWTimeout

from app.config import settings

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.linkedin.com/login"
FEED_SELECTOR = "div.feed-shared-update-v2"
MAX_SCROLL_ATTEMPTS = 20  # increased to support wider date ranges


async def _login(page: Page) -> bool:
    """Attempt to log into LinkedIn. Returns True on success."""
    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
        await page.fill("#username", settings.LINKEDIN_EMAIL)
        await page.fill("#password", settings.LINKEDIN_PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_url("**/feed/**", timeout=20_000)
        logger.info("LinkedIn login successful.")
        return True
    except PWTimeout:
        logger.warning("LinkedIn login timed out - may already be logged in or CAPTCHA present.")
        return False
    except Exception as exc:
        logger.error("LinkedIn login failed: %s", exc)
        return False


async def _extract_post_data(update_element) -> Optional[dict]:
    """Extract fields from a single feed-shared-update-v2 element."""
    try:
        # Post text
        text_el = await update_element.query_selector(
            "div.feed-shared-update-v2__description-wrapper span[dir='ltr']"
        )
        post_text = (await text_el.inner_text()).strip() if text_el else None

        # Canonical post link (activity URN link)
        link_el = await update_element.query_selector(
            "a.app-aware-link[href*='/posts/'], a[href*='activity-']"
        )
        post_link = None
        if link_el:
            raw_href = await link_el.get_attribute("href")
            post_link = raw_href.split("?")[0] if raw_href else None

        if not post_link:
            urn = await update_element.get_attribute("data-urn")
            if urn:
                post_link = f"https://www.linkedin.com/feed/update/{urn}/"

        # Image
        img_el = await update_element.query_selector(
            "img.ivm-view-attr__img--centered, div.update-components-image img"
        )
        image_url = await img_el.get_attribute("src") if img_el else None

        # Timestamp
        time_el = await update_element.query_selector(
            "span.update-components-actor__sub-description span[aria-hidden='true']"
        )
        timestamp_str = (await time_el.inner_text()).strip() if time_el else None
        timestamp = _parse_relative_timestamp(timestamp_str)

        if not post_link:
            logger.debug("Skipping update element - could not determine post_link.")
            return None

        return {
            "post_link": post_link,
            "post_text": post_text,
            "image_url": image_url,
            "timestamp": timestamp,
        }
    except Exception as exc:
        logger.warning("Failed to extract post data from element: %s", exc)
        return None


def _parse_relative_timestamp(text: Optional[str]) -> Optional[datetime]:
    """
    Convert LinkedIn relative time strings like '2h', '3d', '1w' to UTC datetime.
    Returns None when unparseable.
    """
    if not text:
        return None
    now = datetime.now(timezone.utc)
    text = text.strip().lower()
    match = re.search(r"(\d+)\s*([smhdw])", text)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    deltas = {
        "s": timedelta(seconds=value),
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
        "w": timedelta(weeks=value),
    }
    delta = deltas.get(unit)
    return (now - delta) if delta else None


async def scrape_source(
    url: str,
    max_posts: int = 100,
    since_date: Optional[datetime] = None,
) -> list[dict]:
    """
    Scrape posts from a LinkedIn profile or company page.

    Args:
        url: The LinkedIn posts feed URL, e.g.
             https://www.linkedin.com/company/gamigion/posts/?feedView=all
        max_posts: Hard upper limit on the number of posts to collect per run.
        since_date: Timezone-aware UTC datetime acting as the oldest-post cutoff.
                    LinkedIn feeds are newest-first, so once a post older than
                    this date is encountered scrolling stops immediately.
                    Pass None to collect all posts up to max_posts.

    Returns:
        List of dicts with keys: post_link, post_text, image_url, timestamp.
    """
    if since_date is not None:
        logger.info(
            "Scraping %s - collecting posts from %s back to %s.",
            url,
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            since_date.strftime("%Y-%m-%d"),
        )
    else:
        logger.info("Scraping %s - no date cutoff, collecting up to %d posts.", url, max_posts)

    posts: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        await _login(page)

        logger.info("Navigating to source URL: %s", url)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PWTimeout:
            logger.error("Timed out loading source URL: %s", url)
            await browser.close()
            return posts

        seen_links: set[str] = set()
        scroll_attempts = 0
        hit_cutoff = False

        while len(posts) < max_posts and scroll_attempts < MAX_SCROLL_ATTEMPTS and not hit_cutoff:
            await page.wait_for_timeout(2000)

            update_elements = await page.query_selector_all(FEED_SELECTOR)
            logger.debug(
                "Scroll %d: found %d feed elements, collected %d posts so far.",
                scroll_attempts, len(update_elements), len(posts),
            )

            for el in update_elements:
                if len(posts) >= max_posts:
                    break

                data = await _extract_post_data(el)
                if not data or not data["post_link"]:
                    continue

                if data["post_link"] in seen_links:
                    continue

                # Date cutoff check.
                # LinkedIn feeds are newest-first; the moment we see a post
                # older than since_date, everything below will also be older.
                if since_date is not None and data["timestamp"] is not None:
                    if data["timestamp"] < since_date:
                        logger.info(
                            "Post dated %s is before cutoff %s - stopping scroll.",
                            data["timestamp"].strftime("%Y-%m-%d"),
                            since_date.strftime("%Y-%m-%d"),
                        )
                        hit_cutoff = True
                        break

                seen_links.add(data["post_link"])
                posts.append(data)
                logger.debug("Collected post: %s (ts=%s)", data["post_link"], data["timestamp"])

            if hit_cutoff:
                break

            prev_element_count = len(update_elements)
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            scroll_attempts += 1

            await page.wait_for_timeout(2500)
            new_elements = await page.query_selector_all(FEED_SELECTOR)
            if len(new_elements) == prev_element_count:
                logger.info("No new elements after scroll - feed exhausted.")
                break

        logger.info(
            "Finished scraping %s: %d post(s) collected, cutoff reached=%s.",
            url, len(posts), hit_cutoff,
        )
        await browser.close()

    return posts
