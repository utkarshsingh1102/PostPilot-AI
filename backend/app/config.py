import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/postpilot")

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

    # Google / Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # LinkedIn credentials (required for Playwright login)
    LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD", "")

    # Scheduler
    SCRAPE_INTERVAL_HOURS: int = int(os.getenv("SCRAPE_INTERVAL_HOURS", "2"))
    # Oldest post date to scrape (YYYY-MM-DD). Posts before this date are ignored.
    # Defaults to 2026-03-05 for the initial test run; set to "" to disable the cutoff.
    SCRAPE_SINCE_DATE: str = os.getenv("SCRAPE_SINCE_DATE", "2026-03-05")

    @property
    def scrape_since_datetime(self) -> datetime | None:
        """Return SCRAPE_SINCE_DATE as a timezone-aware UTC datetime, or None if unset."""
        if not self.SCRAPE_SINCE_DATE:
            return None
        return datetime.strptime(self.SCRAPE_SINCE_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    # Storage
    GENERATED_IMAGES_DIR: str = os.getenv("GENERATED_IMAGES_DIR", "generated_images")

    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()
