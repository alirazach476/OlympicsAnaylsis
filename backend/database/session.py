"""Engine and session factory."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings
from backend import memdb as _memory

_settings = get_settings()
if _memory.CONN is not None:
    # Serverless deployment: every query runs on the pre-loaded, read-only in-memory warehouse
    # (deploy/vercel-api/api/index.py). One shared connection; SQLite serialises access internally.
    engine = create_engine("sqlite://", creator=lambda: _memory.CONN, poolclass=StaticPool, future=True)
else:
    _connect_args = {}
    if _settings.database_url.startswith("sqlite"):
        _connect_args = {"timeout": 60, "check_same_thread": False}
    engine = create_engine(
        _settings.database_url,
        pool_pre_ping=True,
        future=True,
        connect_args=_connect_args,
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
