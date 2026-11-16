"""Create database schema without Alembic (useful for local SQLite smoke tests)."""

from __future__ import annotations

import logging

from backend.database.base import Base
from backend.database.session import engine
import backend.models  # noqa: F401

logger = logging.getLogger(__name__)


def create_schema() -> None:
    logger.info("Creating database schema on %s", engine.url)
    Base.metadata.create_all(bind=engine)
