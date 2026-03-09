"""
PostPilot-AI – FastAPI application entrypoint.

Startup sequence:
  1. Initialise database tables (SQLAlchemy create_all).
  2. Mount static file serving for generated images.
  3. Register all API routes.
  4. Start the APScheduler background scheduler.

Shutdown:
  - Scheduler is gracefully stopped.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.api.routes import router
from app.scheduler.cron_jobs import setup_scheduler
from app.logging_config import configure_logging

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
configure_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("PostPilot-AI starting up…")
    init_db()

    # Ensure generated images directory exists
    images_dir = Path(settings.GENERATED_IMAGES_DIR)
    images_dir.mkdir(parents=True, exist_ok=True)

    # Start scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Scheduler started.")

    yield

    # ---- Shutdown ----
    logger.info("PostPilot-AI shutting down…")
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PostPilot-AI",
    description=(
        "Backend API for monitoring LinkedIn sources, scraping posts, "
        "rewriting content with Claude, generating images with Gemini, "
        "and serving ready-to-use content through REST endpoints.\n\n"
        "**Important:** This system NEVER publishes to LinkedIn. "
        "All generated content is for manual copy/download only."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS – allow any origin in development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated images as static files at /images/<filename>
_images_dir = Path(settings.GENERATED_IMAGES_DIR)
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(_images_dir)), name="images")

# API routes
app.include_router(router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Dev server entry (python -m app.main or uvicorn app.main:app)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
