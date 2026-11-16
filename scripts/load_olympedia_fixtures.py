#!/usr/bin/env python3
"""Load Olympedia match JSON fixtures from data/raw/olympedia into the warehouse."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.database.session import SessionLocal
from backend.scrapers.olympedia.results import MatchFixture, OlympediaResultsScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games-id", action="append", dest="games_ids")
    args = p.parse_args()

    root = Path("data/raw/olympedia/editions")
    session = SessionLocal()
    scraper = OlympediaResultsScraper(session, delay=0)
    loaded = 0
    files = []
    for edition_dir in sorted(root.glob("*")):
        if args.games_ids and edition_dir.name not in args.games_ids:
            continue
        files.extend(sorted((edition_dir / "matches").glob("*.json")))

    before = session.execute(text("select count(*) from matches")).scalar()
    for i, path in enumerate(files, 1):
        data = json.loads(path.read_text(encoding="utf-8"))
        fx = MatchFixture(**{k: data.get(k) for k in MatchFixture.__dataclass_fields__})
        for attempt in range(10):
            try:
                if scraper.load_fixture(fx):
                    loaded += 1
                if i % 25 == 0:
                    session.commit()
                break
            except OperationalError:
                session.rollback()
                time.sleep(0.4 * (attempt + 1))
        if i % 100 == 0:
            logging.info("loaded %s/%s", loaded, i)
    for attempt in range(10):
        try:
            session.commit()
            break
        except OperationalError:
            session.rollback()
            time.sleep(0.5 * (attempt + 1))
    after = session.execute(text("select count(*) from matches")).scalar()
    session.close()
    print(json.dumps({"match_files": len(files), "loaded_ops": loaded, "before": before, "after": after}, indent=2))


if __name__ == "__main__":
    main()
