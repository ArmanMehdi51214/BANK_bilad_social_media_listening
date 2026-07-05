from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def get_database_url() -> str:
    """
    Production-safe database URL resolver.

    Render provides DATABASE_URL as an environment variable.
    Local development falls back to settings.DATABASE_URL from .env/config.
    """
    return os.getenv("DATABASE_URL") or settings.DATABASE_URL


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

