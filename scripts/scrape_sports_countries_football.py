#!/usr/bin/env python3
"""From each edition Wikipedia main page:
- calendar
- sport hyperlinks (+ event sublinks like 100m)
- participating country hyperlinks
- deep football scrape (scores, squads)

Also reports what was already present vs newly collected.
"""

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
from backend.scrapers.wikipedia.edition_graph import EditionGraphScraper
from backend.scrapers.wikipedia.football import FootballOlympicsScraper
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def counts(session):
    def c(sql):
        return session.execute(text(sql)).scalar()

    return {
        "matches": c("select count(*) from matches"),
        "match_results": c("select count(*) from match_results"),
        "teams": c("select count(*) from teams"),
        "team_members": c("select count(*) from team_members"),
        "events": c("select count(*) from events"),
        "sports": c("select count(*) from sports"),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games-id", action="append", dest="games_ids")
    p.add_argument("--skip-graph", action="store_true")
    p.add_argument("--skip-football", action="store_true")
    p.add_argument("--max-event-pages", type=int, default=25)
    args = p.parse_args()

    session = SessionLocal()
    before = counts(session)
    try:
        graph_summary = None
        football_summary = None

        if not args.skip_graph:
            scraper = EditionGraphScraper(session)
            editions = (
                [get_edition(g) for g in args.games_ids]
                if args.games_ids
                else all_editions()
            )
            results = []
            for edition in editions:
                logging.info("Graph scrape %s", edition.games_id)
                try:
                    results.append(
                        {
                            "ok": True,
                            **scraper.scrape_edition(
                                edition,
                                follow_sports=True,
                                fetch_event_pages=True,
                                max_event_pages=args.max_event_pages,
                            ),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    logging.exception(edition.games_id)
                    results.append({"ok": False, "games_id": edition.games_id, "error": str(exc)})
            graph_summary = {
                "editions_ok": sum(1 for r in results if r.get("ok")),
                "results": [
                    {
                        "games_id": r.get("games_id"),
                        "ok": r.get("ok"),
                        "sports_count": r.get("sports_count"),
                        "countries_count": r.get("countries_count"),
                        "calendar_rows": r.get("calendar_rows"),
                        "event_pages_fetched": r.get("event_pages_fetched"),
                        "countries_fetched": r.get("countries_fetched"),
                        "error": r.get("error"),
                    }
                    for r in results
                ],
            }
            Path("reports/scraping/edition_graph_summary.json").write_text(
                json.dumps(graph_summary, indent=2, default=str), encoding="utf-8"
            )

        if not args.skip_football:
            fb = FootballOlympicsScraper(session)
            if args.games_ids:
                football_summary = {"results": []}
                for gid in args.games_ids:
                    edition = get_edition(gid)
                    football_summary["results"].append(
                        {"ok": True, **fb.scrape_edition(edition)}
                    )
            else:
                football_summary = fb.scrape_all_summer()

        after = counts(session)
        payload = {
            "already_had_before": {
                **before,
                "note": (
                    "Athlete/event/medal rows already existed from historical CSV. "
                    "Matches/squads were 0. Sport hyperlink graph + football scores/squads are new."
                ),
            },
            "after": after,
            "delta": {k: after[k] - before[k] for k in after},
            "graph": graph_summary,
            "football": football_summary,
        }
        Path("reports/scraping/sports_countries_football.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        print(json.dumps(payload, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
