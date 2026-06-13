"""FastAPI application entrypoint.

Run from the backend/ directory:
    uvicorn app.main:app --reload --port 8000
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import categorize, crud, schemas
from .database import Base, engine, get_db

# Create tables on startup. Fine for SQLite single-user dev; swap to Alembic
# migrations if/when the schema needs to evolve in production.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="YouTube Focus Mode API", version="1.0.0")

# No auth yet (single local user), so we allow any origin — this lets both the
# extension's chrome-extension:// popup and its service worker reach the API.
# TIGHTEN THIS to the specific extension origin once auth is introduced.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _format_duration(seconds: int) -> str:
    """Seconds -> "1h 23m" / "5m" / "12s" (mirrors the popup's formatDuration)."""
    s = int(seconds or 0)
    if s < 60:
        return f"{s}s"
    h, m = divmod(s // 60, 60)
    return f"{h}h {m}m" if h else f"{m}m"


@app.get("/")
def home():
    return {
        "message": "YouTube Productivity API Running",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/stats",
            "/api/events",
            "/api/stats/summary",
            "/api/categorize",
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Simple live snapshot (real data) in an easy-to-read shape."""
    q = crud.get_quick_stats(db)
    return {
        "videos_watched": q["videos_watched"],
        "watch_time": _format_duration(q["total_seconds"]),
        "today": _format_duration(q["today_seconds"]),
        "total_seconds": q["total_seconds"],
    }


@app.post("/api/events", response_model=schemas.IngestResponse)
def ingest_events(payload: schemas.IngestRequest, db: Session = Depends(get_db)):
    accepted = crud.add_events(db, payload.events)
    return schemas.IngestResponse(accepted=accepted)


@app.get("/api/stats/summary", response_model=schemas.Summary)
def stats_summary(days: int = 7, db: Session = Depends(get_db)):
    days = max(1, min(days, 90))
    return crud.get_summary(db, days=days)


@app.post("/api/categorize", response_model=schemas.CategorizeResponse)
def categorize_endpoint(limit: int = 50, db: Session = Depends(get_db)):
    """Categorize a batch of so-far-uncategorized videos via Claude (Haiku 4.5).

    Degrades gracefully: with no ANTHROPIC_API_KEY set, returns configured=False
    and categorizes nothing rather than erroring.
    """
    limit = max(1, min(limit, 200))
    pending = crud.get_uncategorized_videos(db, limit=limit)

    if not categorize.is_configured():
        return schemas.CategorizeResponse(
            configured=False, categorized=0, remaining=len(pending)
        )
    if not pending:
        return schemas.CategorizeResponse(configured=True, categorized=0, remaining=0)

    mapping = categorize.categorize_videos(pending)
    titles = {v["video_id"]: v["title"] for v in pending}
    saved = crud.save_categories(db, mapping, titles)
    remaining = len(crud.get_uncategorized_videos(db, limit=1))
    return schemas.CategorizeResponse(
        configured=True, categorized=saved, remaining=remaining
    )
