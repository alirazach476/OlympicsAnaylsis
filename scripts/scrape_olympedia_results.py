#!/usr/bin/env python3
"""Scrape Olympedia Results-by-Games for Summer/Winter 1960–2026.

Source index: https://www.olympedia.org/editions/results

Collects:
  - edition event catalogs
  - event result pages (standings JSON on disk)
  - nested Match # fixtures → matches / match_results tables

Athlete-level CSV results already in warehouse are left intact; this adds
Olympedia URLs, event catalogs, and match fixtures (previously 0).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from backend.database.session import SessionLocal
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS, all_scoped_editions
from backend.scrapers.olympedia.results import OlympediaResultsScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


TEAM_SPORTS = {
    "Football",
    "Handball",
    "Basketball",
    "Basketball (3x3)",
    "3x3 Basketball",
    "Volleyball",
    "Beach Volleyball",
    "Water Polo",
    "Hockey",
    "Field Hockey",
    "Rugby",
    "Rugby Sevens",
    "Baseball",
    "Softball",
    "Baseball/Softball",
    "Ice Hockey",
    "Curling",
    "Lacrosse",
}


def counts(session):
    def c(sql):
        return session.execute(text(sql)).scalar()

    return {
        "matches": c("select count(*) from matches"),
        "match_results": c("select count(*) from match_results"),
        "teams": c("select count(*) from teams"),
        "events": c("select count(*) from events"),
        "olympedia_match_urls": c(
            "select count(*) from matches where source_url like '%olympedia.org%'"
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games-id", action="append", dest="games_ids")
    p.add_argument("--max-events", type=int, default=None)
    p.add_argument(
        "--team-sports-only",
        action="store_true",
        help="Only scrape team sports that typically have Match # fixtures",
    )
    p.add_argument("--sport", action="append", dest="sports")
    p.add_argument("--no-db", action="store_true")
    p.add_argument("--force-refresh", action="store_true")
    p.add_argument("--delay", type=float, default=0.25)
    p.add_argument("--no-skip-done", action="store_true", help="Re-process cached events (uses cached HTML) so new Bout/Game links get followed")
    p.add_argument("--catalog-only", action="store_true")
    p.add_argument(
        "--no-matches",
        action="store_true",
        help="Scrape event standings only; do not follow Match # fixture links",
    )
    p.add_argument(
        "--winter-only",
        action="store_true",
        help="Only winter editions",
    )
    p.add_argument(
        "--summer-only",
        action="store_true",
        help="Only summer editions",
    )
    args = p.parse_args()

    session = None if args.no_db else SessionLocal()
    before = counts(session) if session else {}
    scraper = OlympediaResultsScraper(
        session, delay=args.delay, force_refresh=args.force_refresh
    )

    if args.games_ids:
        targets = [(g, OLYMPEDIA_EDITION_IDS[g]) for g in args.games_ids]
    else:
        targets = all_scoped_editions()
    if args.winter_only:
        targets = [(g, i) for g, i in targets if g.endswith("_winter")]
    if args.summer_only:
        targets = [(g, i) for g, i in targets if g.endswith("_summer")]

    sports = set(args.sports or [])
    if args.team_sports_only:
        sports |= TEAM_SPORTS

    summaries = []
    try:
        for games_id, eid in targets:
            logging.info("Olympedia scrape %s (edition %s)", games_id, eid)
            if args.catalog_only:
                events = scraper.scrape_edition_catalog(games_id)
                summaries.append(
                    {
                        "games_id": games_id,
                        "olympedia_edition_id": eid,
                        "catalog_events": len(events),
                        "mode": "catalog_only",
                    }
                )
                continue
            summary = scraper.scrape_edition(
                games_id,
                follow_matches=not args.no_matches,
                max_events=args.max_events,
                sports=sports or None,
                load_db=not args.no_db,
                skip_done=not args.no_skip_done,
            )
            summaries.append(summary)
            logging.info("done %s %s", games_id, summary)
    finally:
        after = counts(session) if session else {}
        if session:
            session.close()

    report = {
        "before": before,
        "after": after,
        "summaries": summaries,
        "source_index": "https://www.olympedia.org/editions/results",
    }
    out = Path("data/exports/olympedia_scrape_report.json" if not args.games_ids and not (args.winter_only or args.summer_only) else f"data/exports/olympedia_scrape_report_{'_'.join(args.games_ids or ['winter' if args.winter_only else 'summer'])}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
