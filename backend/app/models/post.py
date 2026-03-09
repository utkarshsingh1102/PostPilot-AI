from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ApprovalStatus(str, enum.Enum):
    pending_review = "pending_review"  # freshly scraped, awaiting admin decision
    approved = "approved"              # admin approved — eligible for AI processing
    rejected = "rejected"              # admin rejected — will not be processed


class ScrapedPost(Base):
    """Raw post data extracted from a LinkedIn source."""

    __tablename__ = "scraped_posts"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    post_link = Column(String, unique=True, nullable=False, index=True)
    post_text = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=True)
    approval_status = Column(
        SAEnum(ApprovalStatus),
        default=ApprovalStatus.pending_review,
        nullable=False,
        index=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source = relationship("Source", backref="scraped_posts")
    processed = relationship("ProcessedPost", back_populates="scraped_post", uselist=False)


class ProcessedPost(Base):
    """AI-rewritten and image-generated version of a scraped post."""

    __tablename__ = "processed_posts"

    id = Column(Integer, primary_key=True, index=True)
    scraped_post_id = Column(Integer, ForeignKey("scraped_posts.id", ondelete="SET NULL"), unique=True, nullable=True, index=True)
    source_id = Column(Integer, nullable=True, index=True)   # denormalized – survives source deletion
    source_label = Column(String, nullable=True)              # denormalized – survives source deletion
    rewritten_post = Column(Text, nullable=True)
    hooks = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)  # list of strings
    generated_image_url = Column(String, nullable=True)
    status = Column(SAEnum(ProcessingStatus), default=ProcessingStatus.pending, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    scraped_post = relationship("ScrapedPost", back_populates="processed")
