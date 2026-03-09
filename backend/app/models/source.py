from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class Source(Base):
    """A LinkedIn profile or company page URL that the system monitors."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    linkedin_url = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=True)  # friendly name shown in the sidebar chat list
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
