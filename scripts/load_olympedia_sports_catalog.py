#!/usr/bin/env python3
"""Load Olympedia events_catalog.json into sports + events (clean, not countries)."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from backend.collectors.editions import all_editions
from backend.database.session import SessionLocal
from backend.models.core import Event, Sport

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def gender_of(event_name: str) -> str | None:
    low = event_name.lower()
    if ", men" in low or low.endswith(" men"):
        return "Men"
    if ", women" in low or low.endswith(" women"):
        return "Women"
    if "mixed" in low:
        return "Mixed"
    return None


def ensure_sport(session, name: str, season: str) -> Sport:
    sport = session.scalar(select(Sport).where(Sport.sport_name == name))
    if sport:
        if not sport.season:
            sport.season = season
        if not sport.source_url or "olympedia.org" not in (sport.source_url or ""):
            sport.source_url = "https://www.olympedia.org"
        return sport
    sport = Sport(
        sport_name=name,
        season=season,
        source_url="https://www.olympedia.org",
        verification_status="collected",
    )
    session.add(sport)
    session.flush()
    return sport


def load_catalog(session, games_id: str, season: str, path: Path) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8"))
    sports_seen = set()
    events_added = 0
    events_updated = 0
    for row in rows:
        sport_name = (row.get("sport_name") or "").strip()
        event_name = (row.get("event_name") or "").strip()
        url = row.get("url")
        if not sport_name or not event_name:
            continue
        # skip sport header-like empties
        sports_seen.add(sport_name)
        sport = ensure_sport(session, sport_name, season)
        gender = gender_of(event_name)
        existing = session.scalar(
            select(Event).where(
                Event.games_id == games_id,
                Event.sport_id == sport.sport_id,
                Event.event_name == event_name,
            )
        )
        if existing:
            if url and (not existing.source_url or "olympedia.org" not in existing.source_url):
                existing.source_url = url
                events_updated += 1
            continue
        session.add(
            Event(
                games_id=games_id,
                sport_id=sport.sport_id,
                discipline_id=None,
                event_name=event_name,
                event_gender=gender,
                source_url=url,
                verification_status="collected",
            )
        )
        events_added += 1
    return {
        "games_id": games_id,
        "catalog_rows": len(rows),
        "sports": len(sports_seen),
        "events_added": events_added,
        "events_updated": events_updated,
    }


def purge_country_sports(session) -> int:
    """Remove Sport rows that are clearly countries (wiki graph pollution)."""
    # Keep sports that appear in olympedia catalogs or athlete CSV-linked sports
    keep_names = set()
    root = Path("data/raw/olympedia/editions")
    for cat in root.glob("*/events_catalog.json"):
        for row in json.loads(cat.read_text(encoding="utf-8")):
            if row.get("sport_name"):
                keep_names.add(row["sport_name"])
    # also keep names referenced by event_results
    for name, in session.execute(
        text(
            """
            select distinct s.sport_name from sports s
            join event_results er on er.sport_id = s.sport_id
            """
        )
    ):
        keep_names.add(name)
    for name, in session.execute(
        text(
            """
            select distinct s.sport_name from sports s
            join events e on e.sport_id = s.sport_id
            where e.source_url like '%olympedia.org%'
            """
        )
    ):
        keep_names.add(name)

    deleted = 0
    sports = session.scalars(select(Sport)).all()
    for sport in sports:
        src = sport.source_url or ""
        # polluted: wikipedia country-at-games pages
        if "_at_the_" in src and "Olympics" in src and sport.sport_name not in keep_names:
            # only delete if no event_results / matches point here
            er = session.execute(
                text("select count(*) from event_results where sport_id=:id"),
                {"id": sport.sport_id},
            ).scalar()
            mt = session.execute(
                text("select count(*) from matches where sport_id=:id"),
                {"id": sport.sport_id},
            ).scalar()
            ev = session.execute(
                text("select count(*) from events where sport_id=:id"),
                {"id": sport.sport_id},
            ).scalar()
            if er == 0 and mt == 0 and ev == 0:
                session.delete(sport)
                deleted += 1
    return deleted


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games-id", action="append", dest="games_ids")
    p.add_argument("--purge-country-sports", action="store_true")
    args = p.parse_args()

    session = SessionLocal()
    summaries = []
    try:
        editions = all_editions()
        if args.games_ids:
            editions = [ed for ed in editions if ed.games_id in args.games_ids]
        for ed in editions:
            path = Path("data/raw/olympedia/editions") / ed.games_id / "events_catalog.json"
            if not path.exists():
                summaries.append({"games_id": ed.games_id, "skipped": "no_catalog"})
                continue
            for attempt in range(8):
                try:
                    summaries.append(load_catalog(session, ed.games_id, ed.season, path))
                    session.commit()
                    break
                except OperationalError:
                    session.rollback()
                    time.sleep(0.5 * (attempt + 1))
        purged = 0
        if args.purge_country_sports:
            for attempt in range(8):
                try:
                    purged = purge_country_sports(session)
                    session.commit()
                    break
                except OperationalError:
                    session.rollback()
                    time.sleep(0.5 * (attempt + 1))
        sports_n = session.execute(text("select count(*) from sports")).scalar()
        events_n = session.execute(
            text("select count(*) from events where source_url like '%olympedia.org%'")
        ).scalar()
    finally:
        session.close()

    report = {
        "summaries": summaries,
        "purged_country_sports": purged if args.purge_country_sports else None,
        "sports_total": sports_n,
        "events_with_olympedia_url": events_n,
    }
    out = Path("data/exports/olympedia_sports_catalog_load.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
