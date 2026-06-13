"""SQLAlchemy ORM models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WatchEvent(Base):
    """One chunk of watch time for a single video.

    The extension sends these in batches; many small events per video are fine
    and are aggregated at query time.
    """

    __tablename__ = "watch_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    channel: Mapped[str | None] = mapped_column(String(256), nullable=True)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class VideoCategory(Base):
    """One AI-assigned topic category per distinct video.

    Populated lazily by the /api/categorize endpoint (one Claude call per
    batch of uncategorized videos), then joined against WatchEvent to produce
    time-per-category stats.
    """

    __tablename__ = "video_categories"

    video_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    category: Mapped[str] = mapped_column(String(64), index=True)
    categorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
