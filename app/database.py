"""SQLAlchemy sync engine, session factory, declarative base, and DB helpers."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


engine = create_engine(
    settings.supabase_db_url,
    pool_pre_ping=True,  # drops stale connections before reuse
    echo=settings.debug,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db():
    """FastAPI dependency that yields a DB session and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables defined on Base.metadata (called at app startup)."""
    from app import models  # noqa: F401 — registers models on Base.metadata

    Base.metadata.create_all(bind=engine)
