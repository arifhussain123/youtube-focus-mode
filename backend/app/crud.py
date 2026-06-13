"""Database operations (kept ORM-portable so SQLite -> Postgres is painless)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas


def add_events(db: Session, events: list[schemas.WatchEventIn]) -> int:
    """Insert a batch of watch events. Returns the count accepted."""
    rows = []
    for e in events:
        if e.seconds <= 0:
            continue
        occurred = e.occurred_at or datetime.now(timezone.utc)
        rows.append(
            models.WatchEvent(
                video_id=e.video_id,
                title=e.title or "",
                channel=e.channel,
                seconds=e.seconds,
                occurred_at=occurred,
            )
        )
    if rows:
        db.add_all(rows)
        db.commit()
    return len(rows)


def get_uncategorized_videos(db: Session, limit: int = 50) -> list[dict]:
    """Distinct watched videos that don't yet have a category, newest first."""
    categorized = select(models.VideoCategory.video_id)
    rows = db.execute(
        select(
            models.WatchEvent.video_id,
            func.max(models.WatchEvent.title),
            func.max(models.WatchEvent.channel),
        )
        .where(models.WatchEvent.video_id.not_in(categorized))
        .group_by(models.WatchEvent.video_id)
        .order_by(func.max(models.WatchEvent.occurred_at).desc())
        .limit(limit)
    ).all()
    return [{"video_id": r[0], "title": r[1] or "", "channel": r[2]} for r in rows]


def save_categories(db: Session, mapping: dict[str, str], titles: dict[str, str]) -> int:
    """Insert VideoCategory rows for newly categorized videos."""
    count = 0
    for video_id, category in mapping.items():
        db.add(
            models.VideoCategory(
                video_id=video_id,
                title=titles.get(video_id, ""),
                category=category,
            )
        )
        count += 1
    if count:
        db.commit()
    return count


def get_quick_stats(db: Session) -> dict:
    """Lightweight totals for the simple GET /stats endpoint."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    videos_watched = int(
        db.execute(
            select(func.count(func.distinct(models.WatchEvent.video_id)))
        ).scalar_one()
    )
    total_seconds = int(
        db.execute(
            select(func.coalesce(func.sum(models.WatchEvent.seconds), 0))
        ).scalar_one()
    )
    today_seconds = int(
        db.execute(
            select(func.coalesce(func.sum(models.WatchEvent.seconds), 0)).where(
                models.WatchEvent.occurred_at >= today_start
            )
        ).scalar_one()
    )
    return {
        "videos_watched": videos_watched,
        "total_seconds": total_seconds,
        "today_seconds": today_seconds,
    }


# Group by calendar day in UTC. func.date() works on both SQLite and Postgres.
def _day_expr():
    return func.date(models.WatchEvent.occurred_at)


def get_summary(db: Session, days: int = 7, top: int = 5) -> schemas.Summary:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)  # last 7 calendar days incl. today
    window_start = today_start - timedelta(days=days - 1)

    def _sum_since(start: datetime) -> int:
        stmt = select(func.coalesce(func.sum(models.WatchEvent.seconds), 0)).where(
            models.WatchEvent.occurred_at >= start
        )
        return int(db.execute(stmt).scalar_one())

    today_seconds = _sum_since(today_start)
    week_seconds = _sum_since(week_start)
    total_seconds = int(
        db.execute(
            select(func.coalesce(func.sum(models.WatchEvent.seconds), 0))
        ).scalar_one()
    )

    # Per-day totals across the requested window.
    day = _day_expr()
    daily_rows = db.execute(
        select(day.label("d"), func.sum(models.WatchEvent.seconds))
        .where(models.WatchEvent.occurred_at >= window_start)
        .group_by("d")
        .order_by("d")
    ).all()
    by_day = {str(r[0]): int(r[1]) for r in daily_rows}
    daily = [
        schemas.DailyStat(
            date=(window_start + timedelta(days=i)).strftime("%Y-%m-%d"),
            seconds=by_day.get(
                (window_start + timedelta(days=i)).strftime("%Y-%m-%d"), 0
            ),
        )
        for i in range(days)
    ]

    # Top videos in the window.
    video_rows = db.execute(
        select(
            models.WatchEvent.video_id,
            func.max(models.WatchEvent.title),
            func.sum(models.WatchEvent.seconds).label("s"),
        )
        .where(models.WatchEvent.occurred_at >= window_start)
        .group_by(models.WatchEvent.video_id)
        .order_by(func.sum(models.WatchEvent.seconds).desc())
        .limit(top)
    ).all()
    top_videos = [
        schemas.VideoStat(video_id=r[0], title=r[1] or "", seconds=int(r[2]))
        for r in video_rows
    ]

    # Top channels in the window (skip rows with no channel info).
    channel_rows = db.execute(
        select(
            models.WatchEvent.channel,
            func.sum(models.WatchEvent.seconds).label("s"),
        )
        .where(
            models.WatchEvent.occurred_at >= window_start,
            models.WatchEvent.channel.is_not(None),
        )
        .group_by(models.WatchEvent.channel)
        .order_by(func.sum(models.WatchEvent.seconds).desc())
        .limit(top)
    ).all()
    top_channels = [
        schemas.ChannelStat(channel=r[0], seconds=int(r[1])) for r in channel_rows
    ]

    # Time per category in the window. LEFT JOIN so videos not yet categorized
    # are grouped under "Uncategorized" rather than dropped.
    category_label = func.coalesce(models.VideoCategory.category, "Uncategorized")
    category_rows = db.execute(
        select(category_label.label("c"), func.sum(models.WatchEvent.seconds))
        .select_from(models.WatchEvent)
        .join(
            models.VideoCategory,
            models.VideoCategory.video_id == models.WatchEvent.video_id,
            isouter=True,
        )
        .where(models.WatchEvent.occurred_at >= window_start)
        .group_by("c")
        .order_by(func.sum(models.WatchEvent.seconds).desc())
    ).all()
    by_category = [
        schemas.CategoryStat(category=r[0], seconds=int(r[1])) for r in category_rows
    ]

    return schemas.Summary(
        today_seconds=today_seconds,
        week_seconds=week_seconds,
        total_seconds=total_seconds,
        daily=daily,
        top_videos=top_videos,
        top_channels=top_channels,
        by_category=by_category,
    )
