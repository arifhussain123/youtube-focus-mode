"""Database engine/session setup.

Uses SQLite for local dev. Swapping to PostgreSQL later is only a matter of
changing DATABASE_URL (e.g. "postgresql+psycopg://user:pass@host/db") and
removing the SQLite-only connect_args — no model or query changes needed.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# focus.db is created next to the backend/ folder on first run.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(__file__)), "focus.db"),
)

# check_same_thread is a SQLite-only quirk; harmless to gate on the scheme.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
