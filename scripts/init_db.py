#!/usr/bin/env python3
"""Initialize database schema and seed Olympic edition master rows."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.bootstrap import create_schema
from backend.database.session import SessionLocal
from backend.scrapers.wikipedia.crawler import WikipediaOlympicsCrawler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("init_db")


def main() -> None:
    create_schema()
    session = SessionLocal()
    try:
        crawler = WikipediaOlympicsCrawler(session)
        inserted = crawler.ensure_games_rows()
        queued = crawler.seed_queue()
        logger.info("Games inserted: %s | Seed queue added: %s", inserted, queued)
    finally:
        session.close()


if __name__ == "__main__":
    main()
