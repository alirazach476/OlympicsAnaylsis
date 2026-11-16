#!/usr/bin/env python3
"""Deep recursive Wikipedia crawl: follow Olympic links and sublinks (BFS).

This intentionally stays inside the Olympic page network via relevance scoring.
It does NOT crawl the entire encyclopedia.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.collectors.editions import all_editions
from backend.database.bootstrap import create_schema
from backend.database.session import SessionLocal
from backend.scrapers.wikipedia.crawler import CrawlControls, WikipediaOlympicsCrawler
from backend.validators.quality import write_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("deep_wiki_crawl")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games-id", action="append", dest="games_ids")
    p.add_argument("--max-depth", type=int, default=3, help="Link depth from seed pages")
    p.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Max pages to open per Olympic edition",
    )
    p.add_argument("--min-score", type=float, default=0.40)
    p.add_argument("--init-schema", action="store_true")
    p.add_argument("--promote-links", action="store_true", help="Also re-scan every stored link into the queue first (very slow: ~280k links, 2 queries each)")
    args = p.parse_args()

    if args.init_schema:
        create_schema()

    games_ids = args.games_ids or [e.games_id for e in all_editions()]
    session = SessionLocal()
    try:
        crawler = WikipediaOlympicsCrawler(session)
        crawler.resume()
        crawler.ensure_games_rows()
        seeded = crawler.seed_queue(games_ids)
        reclaimed = crawler.reclaim_stale_in_progress()
        reopened = crawler.requeue_skipped_and_failed(games_ids)
        promoted = 0
        if args.promote_links:
            promoted = crawler.enqueue_discovered_olympic_links(
                games_ids, min_score=args.min_score, max_depth=args.max_depth
            )
        logger.info(
            "seeded=%s reclaimed=%s reopened=%s promoted_links=%s",
            seeded,
            reclaimed,
            reopened,
            promoted,
        )

        stats = crawler.run(
            CrawlControls(
                max_depth=args.max_depth,
                max_pages_per_edition=args.max_pages,
                min_relevance_score=args.min_score,
                games_ids=games_ids,
            )
        )
        summary = crawler.summarize()
        reports = write_reports(session)
        payload = {"stats": stats.__dict__, "summary": summary, "reports": reports}
        out = ROOT / "reports/scraping/deep_wiki_crawl_summary.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(json.dumps(payload, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
