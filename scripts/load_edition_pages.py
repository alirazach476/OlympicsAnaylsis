#!/usr/bin/env python3
"""Load missing edition master data from each Olympics Wikipedia main page."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.collectors.editions import all_editions, get_edition
from backend.database.session import SessionLocal
from backend.loaders.wikipedia_edition_pages import WikipediaEditionPageLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games-id", action="append", dest="games_ids")
    args = p.parse_args()
    editions = (
        [get_edition(g) for g in args.games_ids] if args.games_ids else all_editions()
    )
    session = SessionLocal()
    try:
        summary = WikipediaEditionPageLoader(session).load_all(editions)
        print(
            json.dumps(
                {
                    "editions_ok": summary["editions_ok"],
                    "editions_failed": summary["editions_failed"],
                    "report": "reports/scraping/wikipedia_edition_pages.json",
                    "export": "data/exports/games_from_wikipedia.csv",
                    "sample": summary["results"][:3],
                },
                indent=2,
                default=str,
            )
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
