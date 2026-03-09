"""
FastAPI router – all REST endpoints for PostPilot-AI backend.

Endpoint summary:
  POST   /sources              Add a LinkedIn source URL
  GET    /sources              List all sources
  GET    /sources/{id}         Get a single source
  DELETE /sources/{id}         Remove a source

  GET    /posts/raw            List scraped posts (paginated, filterable by source)
  GET    /posts/processed      List processed posts (paginated, filterable by status)
  GET    /posts/{id}           Full processed post detail (dashboard view)

  POST   /process/{id}         Manually trigger processing of a scraped post
  POST   /process-all          Process all pending/failed posts

  GET    /health               Health check
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Source, ScrapedPost, ProcessedPost, ProcessingStatus
from app.api.schemas import (
    SourceCreate, SourceResponse,
    ScrapedPostResponse, ProcessedPostResponse,
    FullPostResponse, ProcessResponse, BulkProcessResponse,
)
from app.services.claude_rewriter import rewrite_post, build_copy_ready_text
from app.services.gemini_image_generator import generate_image, get_download_url
from app.scheduler.cron_jobs import _process_one

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
# Raw scraped posts
# ---------------------------------------------------------------------------

@router.get("/posts/raw", response_model=list[ScrapedPostResponse], tags=["posts"])
def list_raw_posts(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List raw scraped posts, optionally filtered by source."""
    q = db.query(ScrapedPost)
    if source_id is not None:
        q = q.filter(ScrapedPost.source_id == source_id)
    return q.order_by(ScrapedPost.created_at.desc()).offset(offset).limit(limit).all()


# ---------------------------------------------------------------------------
# Processed posts
# ---------------------------------------------------------------------------

@router.get("/posts/processed", response_model=list[ProcessedPostResponse], tags=["posts"])
def list_processed_posts(
    source_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status: pending|processing|completed|failed"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List processed posts with optional filtering."""
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


@router.get("/posts/{post_id}", response_model=FullPostResponse, tags=["posts"])
def get_full_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Return the full enriched post view for the dashboard.
    post_id is the scraped_post id.
    """
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
# Trigger processing
# ---------------------------------------------------------------------------

async def _run_process_one(scraped_post_id: int) -> None:
    """Background task wrapper for processing a single post."""
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
    Processing runs in the background; poll GET /posts/{id} for status.
    """
    scraped = db.query(ScrapedPost).get(post_id)
    if not scraped:
        raise HTTPException(status_code=404, detail="Scraped post not found.")

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
    Trigger processing for all scraped posts that are not yet completed.
    Each post is queued as a separate background task.
    """
    processed_ids = db.query(ProcessedPost.scraped_post_id).filter(
        ProcessedPost.status == ProcessingStatus.completed
    ).subquery()

    pending = db.query(ScrapedPost).filter(ScrapedPost.id.not_in(processed_ids)).all()

    for scraped in pending:
        background_tasks.add_task(_run_process_one, scraped.id)

    logger.info("Bulk processing triggered for %d post(s).", len(pending))
    return BulkProcessResponse(
        triggered=len(pending),
        message=f"Processing queued for {len(pending)} post(s).",
    )
