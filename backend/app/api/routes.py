"""
FastAPI router – all REST endpoints for PostPilot-AI backend.

Endpoint summary:
  POST   /sources                   Add a LinkedIn source URL
  GET    /sources                   List all sources
  GET    /sources/{id}              Get a single source
  DELETE /sources/{id}              Remove a source

  GET    /posts/raw                 List scraped posts (filterable by source, approval_status)
  PATCH  /posts/raw/{id}/review     Approve or reject a scraped post
  GET    /posts/processed           List processed posts (filterable by status)
  GET    /posts/{id}                Full processed post detail (dashboard view)

  POST   /scrape-now                Manually trigger scrape for all (or one) source
  POST   /process/{id}             Process a specific approved post
  POST   /process-all              Process all approved-but-unprocessed posts

  GET    /health                    Health check
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Source, ScrapedPost, ProcessedPost, ProcessingStatus, ApprovalStatus
from app.api.schemas import (
    SourceCreate, SourceResponse,
    ScrapedPostResponse, ProcessedPostResponse,
    FullPostResponse, ProcessResponse, BulkProcessResponse,
    ApprovalAction, ApprovalResponse,
)
from app.services.claude_rewriter import rewrite_post, build_copy_ready_text
from app.services.gemini_image_generator import generate_image, get_download_url
from app.scheduler.cron_jobs import _process_one, scrape_all_sources

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

@router.post("/sources", response_model=SourceResponse, status_code=201, tags=["sources"])
def add_source(payload: SourceCreate, db: Session = Depends(get_db)):
    """Add a new LinkedIn profile or company page URL to monitor."""
    existing = db.query(Source).filter_by(linkedin_url=payload.linkedin_url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Source URL already exists.")
    source = Source(linkedin_url=payload.linkedin_url, label=payload.label)
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info("New source added: id=%d url=%s", source.id, source.linkedin_url)
    return source


@router.get("/sources", response_model=list[SourceResponse], tags=["sources"])
def list_sources(db: Session = Depends(get_db)):
    """Return all monitored LinkedIn sources (sidebar chat list)."""
    return db.query(Source).order_by(Source.created_at.desc()).all()


@router.get("/sources/{source_id}", response_model=SourceResponse, tags=["sources"])
def get_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")
    return source


@router.delete("/sources/{source_id}", status_code=204, tags=["sources"])
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")
    db.delete(source)
    db.commit()
    logger.info("Source deleted: id=%d", source_id)


# ---------------------------------------------------------------------------
# Raw scraped posts — review queue
# ---------------------------------------------------------------------------

@router.get("/posts/raw", response_model=list[ScrapedPostResponse], tags=["review"])
def list_raw_posts(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    approval_status: Optional[str] = Query(
        None,
        description="Filter by approval status: pending_review | approved | rejected"
    ),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List raw scraped posts — the admin review queue.
    By default returns all posts. Use approval_status=pending_review to see
    posts waiting for a decision.
    """
    q = db.query(ScrapedPost)
    if source_id is not None:
        q = q.filter(ScrapedPost.source_id == source_id)
    if approval_status is not None:
        try:
            status_enum = ApprovalStatus(approval_status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid approval_status '{approval_status}'. "
                       "Use: pending_review | approved | rejected"
            )
        q = q.filter(ScrapedPost.approval_status == status_enum)
    return q.order_by(ScrapedPost.created_at.desc()).offset(offset).limit(limit).all()


@router.patch("/posts/raw/{post_id}/review", response_model=ApprovalResponse, tags=["review"])
def review_post(
    post_id: int,
    payload: ApprovalAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Admin endpoint to approve or reject a scraped post.

    - approve  -> marks post as approved and immediately starts AI processing.
    - reject   -> marks post as rejected; it will never be processed.

    Body: { "action": "approve" }  or  { "action": "reject" }
    """
    scraped = db.query(ScrapedPost).get(post_id)
    if not scraped:
        raise HTTPException(status_code=404, detail="Scraped post not found.")

    new_status = (
        ApprovalStatus.approved if payload.action == "approve" else ApprovalStatus.rejected
    )
    scraped.approval_status = new_status
    scraped.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    if new_status == ApprovalStatus.approved:
        background_tasks.add_task(_run_process_one, post_id)
        logger.info("Post id=%d approved — AI processing started automatically.", post_id)
    else:
        logger.info("Post id=%d rejected by admin.", post_id)

    return ApprovalResponse(
        scraped_post_id=post_id,
        approval_status=new_status.value,
        message=f"Post {new_status.value}." + (" AI processing started." if new_status == ApprovalStatus.approved else ""),
    )


# ---------------------------------------------------------------------------
# Processed posts — output dashboard
# ---------------------------------------------------------------------------

@router.get("/posts/processed", response_model=list[ProcessedPostResponse], tags=["dashboard"])
def list_processed_posts(
    source_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="pending | processing | completed | failed"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List processed posts. Only approved posts ever reach this table."""
    q = db.query(ProcessedPost).join(ScrapedPost)
    if source_id is not None:
        q = q.filter(ScrapedPost.source_id == source_id)
    if status:
        try:
            status_enum = ProcessingStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'.")
        q = q.filter(ProcessedPost.status == status_enum)
    return q.order_by(ProcessedPost.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/posts/{post_id}", response_model=FullPostResponse, tags=["dashboard"])
def get_full_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    """Full enriched post view for the dashboard (scraped_post id)."""
    scraped = db.query(ScrapedPost).get(post_id)
    if not scraped:
        raise HTTPException(status_code=404, detail="Post not found.")

    processed = scraped.processed
    base_url = str(request.base_url).rstrip("/")

    download_url = None
    copy_ready = None
    if processed and processed.status == ProcessingStatus.completed:
        download_url = get_download_url(processed.generated_image_url, base_url)
        copy_ready = build_copy_ready_text(
            processed.rewritten_post or "",
            processed.hashtags or [],
        )

    return FullPostResponse(
        scraped_post_id=scraped.id,
        source_id=scraped.source_id,
        post_link=scraped.post_link,
        original_text=scraped.post_text,
        original_image_url=scraped.image_url,
        post_timestamp=scraped.timestamp,
        approval_status=scraped.approval_status.value,
        processed_post_id=processed.id if processed else None,
        rewritten_post=processed.rewritten_post if processed else None,
        hooks=processed.hooks if processed else None,
        hashtags=processed.hashtags if processed else None,
        generated_image_url=processed.generated_image_url if processed else None,
        download_image_url=download_url,
        copy_ready_text=copy_ready,
        status=processed.status.value if processed else "unprocessed",
    )


# ---------------------------------------------------------------------------
# Scrape trigger
# ---------------------------------------------------------------------------

@router.post("/scrape-now", tags=["scraping"])
async def scrape_now(
    background_tasks: BackgroundTasks,
    source_id: Optional[int] = Query(None, description="Scrape a specific source only. Omit to scrape all."),
    db: Session = Depends(get_db),
):
    """
    Manually trigger a LinkedIn scrape right now without waiting for the cron job.
    New posts land in the review queue with status=pending_review.
    Poll GET /posts/raw?approval_status=pending_review to see them.
    """
    if source_id is not None:
        source = db.query(Source).get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found.")

        async def _scrape_one():
            from app.database import SessionLocal as _SL
            from app.models import ScrapedPost as _SP
            from app.services.linkedin_scraper import scrape_source
            _db = _SL()
            since_date = settings.scrape_since_datetime
            try:
                posts = await scrape_source(
                    source.linkedin_url,
                    since_date=since_date,
                    images_dir=settings.GENERATED_IMAGES_DIR,
                )
                new_count = 0
                for p in posts:
                    if not _db.query(_SP).filter_by(post_link=p["post_link"]).first():
                        _db.add(_SP(
                            source_id=source.id,
                            post_link=p["post_link"],
                            post_text=p.get("post_text"),
                            image_url=p.get("image_url"),
                            timestamp=p.get("timestamp"),
                        ))
                        new_count += 1
                _db.commit()
                logger.info("Manual scrape: saved %d new post(s) from source id=%d.", new_count, source.id)
            finally:
                _db.close()

        background_tasks.add_task(_scrape_one)
        return {
            "message": f"Scraping source id={source_id} in background. "
                       "Poll GET /api/v1/posts/raw?approval_status=pending_review to see new posts."
        }

    background_tasks.add_task(scrape_all_sources)
    sources_count = db.query(Source).count()
    return {
        "message": f"Scraping all {sources_count} source(s) in background. "
                   "Poll GET /api/v1/posts/raw?approval_status=pending_review to see new posts."
    }


# ---------------------------------------------------------------------------
# Process (AI pipeline) — only for approved posts
# ---------------------------------------------------------------------------

async def _run_process_one(scraped_post_id: int) -> None:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        scraped = db.query(ScrapedPost).get(scraped_post_id)
        if scraped:
            await _process_one(db, scraped)
    finally:
        db.close()


@router.post("/process/{post_id}", response_model=ProcessResponse, tags=["processing"])
async def process_post(
    post_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Manually trigger AI processing (Claude + Gemini) for a specific scraped post.
    The post MUST be approved first via PATCH /posts/raw/{id}/review.
    """
    scraped = db.query(ScrapedPost).get(post_id)
    if not scraped:
        raise HTTPException(status_code=404, detail="Scraped post not found.")

    if scraped.approval_status != ApprovalStatus.approved:
        raise HTTPException(
            status_code=403,
            detail=f"Post is '{scraped.approval_status.value}'. "
                   "Only approved posts can be processed. "
                   "Use PATCH /posts/raw/{id}/review to approve it first."
        )

    processed = scraped.processed
    if processed and processed.status == ProcessingStatus.completed:
        return ProcessResponse(
            scraped_post_id=post_id,
            status="completed",
            message="Post is already processed.",
        )

    background_tasks.add_task(_run_process_one, post_id)
    logger.info("Manual processing triggered for scraped_post id=%d.", post_id)
    return ProcessResponse(
        scraped_post_id=post_id,
        status="queued",
        message="Processing started in background. Poll GET /posts/{id} for status.",
    )


@router.post("/process-all", response_model=BulkProcessResponse, tags=["processing"])
async def process_all(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Trigger AI processing for all approved posts that are not yet completed.
    Rejected and pending_review posts are completely ignored.
    """
    completed_ids = db.query(ProcessedPost.scraped_post_id).filter(
        ProcessedPost.status == ProcessingStatus.completed
    ).subquery()

    approved_pending = (
        db.query(ScrapedPost)
        .filter(
            ScrapedPost.approval_status == ApprovalStatus.approved,
            ScrapedPost.id.not_in(completed_ids),
        )
        .all()
    )

    for scraped in approved_pending:
        background_tasks.add_task(_run_process_one, scraped.id)

    logger.info("Bulk processing triggered for %d approved post(s).", len(approved_pending))
    return BulkProcessResponse(
        triggered=len(approved_pending),
        message=f"Processing queued for {len(approved_pending)} approved post(s).",
    )
