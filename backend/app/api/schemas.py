"""
Pydantic request/response schemas for all API endpoints.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Source schemas
# ---------------------------------------------------------------------------

class SourceCreate(BaseModel):
    linkedin_url: str
    label: Optional[str] = None

    @field_validator("linkedin_url")
    @classmethod
    def must_be_linkedin(cls, v: str) -> str:
        if "linkedin.com" not in v:
            raise ValueError("URL must be a linkedin.com URL.")
        return v.strip().rstrip("/")


class SourceResponse(BaseModel):
    id: int
    linkedin_url: str
    label: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Scraped post schemas
# ---------------------------------------------------------------------------

class ScrapedPostResponse(BaseModel):
    id: int
    source_id: int
    post_link: str
    post_text: Optional[str]
    image_url: Optional[str]
    timestamp: Optional[datetime]
    approval_status: str
    reviewed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalAction(BaseModel):
    """Request body for approve/reject endpoints."""
    action: str  # "approve" or "reject"

    @field_validator("action")
    @classmethod
    def valid_action(cls, v: str) -> str:
        if v not in ("approve", "reject"):
            raise ValueError("action must be 'approve' or 'reject'.")
        return v


class ApprovalResponse(BaseModel):
    scraped_post_id: int
    approval_status: str
    message: str


# ---------------------------------------------------------------------------
# Image version schemas
# ---------------------------------------------------------------------------

class ImageVersionResponse(BaseModel):
    id: int
    image_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Processed post schemas
# ---------------------------------------------------------------------------

class ProcessedPostResponse(BaseModel):
    id: int
    scraped_post_id: Optional[int]
    source_id: Optional[int]
    source_label: Optional[str]
    rewritten_post: Optional[str]
    hooks: Optional[str]
    hashtags: Optional[list[str]]
    generated_image_url: Optional[str]
    reimagine_status: str = "idle"
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FullPostResponse(BaseModel):
    """Enriched response combining original + processed data for the dashboard."""

    # Scraped (original)
    scraped_post_id: int
    source_id: int
    post_link: str
    original_text: Optional[str]
    original_image_url: Optional[str]
    post_timestamp: Optional[datetime]
    approval_status: str

    # Processed
    processed_post_id: Optional[int]
    rewritten_post: Optional[str]
    hooks: Optional[str]
    hashtags: Optional[list[str]]
    generated_image_url: Optional[str]
    download_image_url: Optional[str]
    copy_ready_text: Optional[str]
    reimagine_status: str = "idle"
    image_versions: list[ImageVersionResponse] = []
    status: str

    model_config = {"from_attributes": True}


class ProcessResponse(BaseModel):
    """Response returned after triggering processing of a post."""
    scraped_post_id: int
    status: str
    message: str


class BulkProcessResponse(BaseModel):
    triggered: int
    message: str


class ReimagineResponse(BaseModel):
    processed_post_id: int
    status: str
    message: str
