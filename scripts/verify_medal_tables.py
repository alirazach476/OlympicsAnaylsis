#!/usr/bin/env python3
"""Verify/load country medal tables from Wikipedia for every 1960–2026 edition."""

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
from backend.loaders.wikipedia_medal_tables import WikipediaMedalTableLoader

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
        summary = WikipediaMedalTableLoader(session).load_all(editions)
        print(json.dumps({
            "editions_ok": summary["editions_ok"],
            "editions_failed": summary["editions_failed"],
            "report": "reports/verification/wikipedia_medal_tables.json",
            "sample_comparisons": summary["comparisons"][:3],
        }, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
