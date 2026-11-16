#!/usr/bin/env python3
"""BFS-crawl Wikipedia seed pages for every 1960–2026 edition (bounded)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.collectors.editions import all_editions
from backend.database.bootstrap import create_schema
from backend.database.session import SessionLocal
from backend.scrapers.wikipedia.crawler import CrawlControls, WikipediaOlympicsCrawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--max-depth", type=int, default=1)
    p.add_argument("--max-pages", type=int, default=15)
    p.add_argument("--min-score", type=float, default=0.5)
    p.add_argument("--init-schema", action="store_true")
    args = p.parse_args()

    if args.init_schema:
        create_schema()

    games_ids = [e.games_id for e in all_editions()]
    session = SessionLocal()
    try:
        crawler = WikipediaOlympicsCrawler(session)
        crawler.ensure_games_rows()
        crawler.seed_queue(games_ids)
        stats = crawler.run(
            CrawlControls(
                max_depth=args.max_depth,
                max_pages_per_edition=args.max_pages,
                min_relevance_score=args.min_score,
                games_ids=games_ids,
            )
        )
        print(stats)
        print(crawler.summarize())
    finally:
        session.close()


if __name__ == "__main__":
    main()
