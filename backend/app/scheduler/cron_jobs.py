"""
APScheduler cron jobs for PostPilot-AI.

Jobs:
  1. scrape_all_sources  – runs every N hours (default 2).
     For each active Source, calls the LinkedIn scraper and saves new posts to DB.

  2. process_pending_posts – runs 10 minutes after each scrape sweep.
     Picks up all scraped posts that have no ProcessedPost yet and runs the
     full Claude + Gemini pipeline on them.

Both jobs are registered in `setup_scheduler()` which is called from main.py.
"""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Source, ScrapedPost, ProcessedPost, ProcessingStatus, ApprovalStatus
from app.services.linkedin_scraper import scrape_source
from app.services.claude_rewriter import rewrite_post, build_copy_ready_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper – process a single scraped post through Claude + Gemini
# ---------------------------------------------------------------------------

async def _process_one(db: Session, scraped: ScrapedPost) -> None:
    """Run the full AI pipeline on a single ScrapedPost. Idempotent."""
    # Create or fetch the ProcessedPost record
    processed = db.query(ProcessedPost).filter_by(scraped_post_id=scraped.id).first()
    if processed is None:
        processed = ProcessedPost(
            scraped_post_id=scraped.id,
            status=ProcessingStatus.pending,
        )
        db.add(processed)
        db.commit()
        db.refresh(processed)

    if processed.status == ProcessingStatus.completed:
        logger.debug("Post %d already processed – skipping.", scraped.id)
        return

    # Mark as processing
    processed.status = ProcessingStatus.processing
    processed.updated_at = datetime.now(timezone.utc)
    db.commit()

    try:
        # ---- Claude rewrite ----
        if not scraped.post_text or not scraped.post_text.strip():
            processed.status = ProcessingStatus.failed
            processed.error_message = (
                "Post has no text content. It may be image-only or the scraper "
                "selector didn't match. Re-scrape or enter text manually."
            )
            processed.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning("[cron] Skipping scraped_post id=%d — no text to rewrite.", scraped.id)
            return

        logger.info("[cron] Rewriting scraped_post id=%d via Claude.", scraped.id)
        rewrite_result = await rewrite_post(scraped.post_text)

        processed.rewritten_post = rewrite_result["rewritten_post"]
        processed.hooks = rewrite_result["hooks"]
        processed.hashtags = rewrite_result["hashtags"]

        # ---- Use scraped image as output ----
        processed.generated_image_url = scraped.image_url

        processed.status = ProcessingStatus.completed
        processed.error_message = None
        logger.info("[cron] Successfully processed scraped_post id=%d.", scraped.id)

    except Exception as exc:
        processed.status = ProcessingStatus.failed
        processed.error_message = str(exc)
        logger.error("[cron] Failed to process scraped_post id=%d: %s", scraped.id, exc)

    processed.updated_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------------------
# Job 1 – Scrape all sources
# ---------------------------------------------------------------------------

async def scrape_all_sources() -> None:
    logger.info("[cron] scrape_all_sources – started at %s", datetime.now(timezone.utc).isoformat())
    db: Session = SessionLocal()
    try:
        sources = db.query(Source).all()
        logger.info("[cron] Found %d source(s) to scrape.", len(sources))

        since_date = settings.scrape_since_datetime
        if since_date:
            logger.info("[cron] Using date cutoff: posts on or after %s.", since_date.strftime("%Y-%m-%d"))

        for source in sources:
            logger.info("[cron] Scraping source id=%d url=%s", source.id, source.linkedin_url)
            try:
                posts = await scrape_source(
                    source.linkedin_url,
                    since_date=since_date,
                    images_dir=settings.GENERATED_IMAGES_DIR,
                )
            except Exception as exc:
                logger.error("[cron] Scraping failed for source %d: %s", source.id, exc)
                continue

            new_count = 0
            for post_data in posts:
                exists = db.query(ScrapedPost).filter_by(post_link=post_data["post_link"]).first()
                if exists:
                    continue
                scraped = ScrapedPost(
                    source_id=source.id,
                    post_link=post_data["post_link"],
                    post_text=post_data.get("post_text"),
                    image_url=post_data.get("image_url"),
                    timestamp=post_data.get("timestamp"),
                )
                db.add(scraped)
                new_count += 1

            db.commit()
            logger.info("[cron] Saved %d new post(s) from source id=%d.", new_count, source.id)

    finally:
        db.close()

    logger.info("[cron] scrape_all_sources – completed.")


# ---------------------------------------------------------------------------
# Job 2 – Process all pending scraped posts
# ---------------------------------------------------------------------------

async def process_pending_posts() -> None:
    logger.info("[cron] process_pending_posts – started at %s", datetime.now(timezone.utc).isoformat())
    db: Session = SessionLocal()
    try:
        # Only process posts that an admin has explicitly approved.
        # pending_review and rejected posts are never auto-processed.
        processed_ids = db.query(ProcessedPost.scraped_post_id).filter(
            ProcessedPost.status == ProcessingStatus.completed
        ).subquery()

        pending = (
            db.query(ScrapedPost)
            .filter(
                ScrapedPost.approval_status == ApprovalStatus.approved,
                ScrapedPost.id.not_in(processed_ids),
            )
            .all()
        )

        logger.info("[cron] %d approved post(s) pending processing.", len(pending))

        for scraped in pending:
            await _process_one(db, scraped)

    finally:
        db.close()

    logger.info("[cron] process_pending_posts – completed.")


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def setup_scheduler() -> AsyncIOScheduler:
    """
    Create, configure, and return the APScheduler instance.
    Call .start() on the returned scheduler from main.py lifespan.
    """
    scheduler = AsyncIOScheduler()

    interval_hours = settings.SCRAPE_INTERVAL_HOURS

    # Job 1: scrape every N hours
    scheduler.add_job(
        scrape_all_sources,
        trigger=IntervalTrigger(hours=interval_hours),
        id="scrape_all_sources",
        name="Scrape all LinkedIn sources",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Job 2: process pending posts – 10 min after scrape sweep (offset), then same interval
    scheduler.add_job(
        process_pending_posts,
        trigger=IntervalTrigger(hours=interval_hours, start_date=None),
        id="process_pending_posts",
        name="Process pending scraped posts",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(
        "Scheduler configured: scraping every %d hour(s), processing runs on same interval.",
        interval_hours,
    )
    return scheduler
