#!/usr/bin/env python3
"""CLI entrypoint for the recursive Wikipedia Olympics BFS crawler."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.bootstrap import create_schema
from backend.database.session import SessionLocal
from backend.scrapers.wikipedia.crawler import CrawlControls, WikipediaOlympicsCrawler
from backend.validators.quality import write_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("crawl_wikipedia")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crawl Olympic Wikipedia page networks")
    p.add_argument(
        "--games-id",
        action="append",
        dest="games_ids",
        help="Limit to one or more games_id values (e.g. 1960_summer). Repeatable.",
    )
    p.add_argument("--max-depth", type=int, default=2)
    p.add_argument("--max-pages", type=int, default=25, help="Max pages per edition")
    p.add_argument("--min-score", type=float, default=0.45)
    p.add_argument("--pause", action="store_true", help="Write pause file and exit")
    p.add_argument("--resume-clear-pause", action="store_true", help="Clear pause file")
    p.add_argument("--seed-only", action="store_true")
    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--init-schema", action="store_true", help="create_all before crawl")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.init_schema:
        create_schema()

    session = SessionLocal()
    try:
        crawler = WikipediaOlympicsCrawler(session)
        if args.pause:
            crawler.pause()
            logger.info("Pause file written")
            return
        if args.resume_clear_pause:
            crawler.resume()
            logger.info("Pause file cleared")

        crawler.ensure_games_rows()
        added = crawler.seed_queue(args.games_ids)
        logger.info("Seed queue additions: %s", added)

        if args.seed_only:
            print(json.dumps(crawler.summarize(), indent=2))
            return
        if args.summary_only:
            print(json.dumps(crawler.summarize(args.games_ids[0] if args.games_ids else None), indent=2))
            return

        stats = crawler.run(
            CrawlControls(
                max_depth=args.max_depth,
                max_pages_per_edition=args.max_pages,
                min_relevance_score=args.min_score,
                games_ids=args.games_ids,
            )
        )
        logger.info("Crawl finished: %s", stats)
        summary = write_reports(session, args.games_ids[0] if args.games_ids else None)
        print(json.dumps({"stats": stats.__dict__, "reports": summary}, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
