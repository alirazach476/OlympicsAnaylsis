#!/usr/bin/env python3
"""Backfill Olympedia phase dropdown pages (Run #N, Standings after Run #N, etc.).

Separate from the main edition scrape. Safe to resume: skips phases/*.json already saved.
Does NOT follow same_games_select / other_games_select navigation menus.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scrapers.olympedia.results import EventRef, OlympediaResultsScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--games-id", action="append", dest="games_ids")
    p.add_argument("--limit-parents", type=int, default=None)
    args = p.parse_args()

    scraper = OlympediaResultsScraper(session=None, delay=args.delay)
    root = Path("data/raw/olympedia/editions")
    parents = sorted(root.glob("*/events/*.html"))
    if args.games_ids:
        allow = set(args.games_ids)
        parents = [p for p in parents if p.parts[-3] in allow]

    parents_with_subs = 0
    phases_new = 0
    phases_skipped = 0
    scanned = 0

    for html_path in parents:
        if args.limit_parents is not None and scanned >= args.limit_parents:
            break
        scanned += 1
        games_id = html_path.parts[-3]
        parent_id = html_path.stem
        html = html_path.read_text(encoding="utf-8", errors="replace")
        subs = scraper.parse_sub_selects(html)
        if not subs:
            continue
        parents_with_subs += 1
        # enrich from sibling json if present
        meta_path = html_path.with_suffix(".json")
        sport = "Unknown"
        event_name = parent_id
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                sport = meta.get("sport_name") or sport
                event_name = meta.get("event_name") or event_name
                # refresh sub links into parent json
                meta["sub_select_links"] = subs
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        # only fetch missing phases
        todo = []
        for link in subs:
            rid = link["result_id"]
            if rid == parent_id:
                continue
            jpath = root / games_id / "phases" / f"{rid}.json"
            if jpath.exists() and jpath.stat().st_size > 80:
                phases_skipped += 1
                continue
            todo.append(link)
        if not todo:
            continue

        ref = EventRef(
            games_id=games_id,
            olympedia_edition_id=0,
            sport_name=sport,
            event_name=event_name,
            result_id=parent_id,
            url=f"https://www.olympedia.org/results/{parent_id}",
        )
        n = scraper.scrape_sub_phases(ref, todo)
        phases_new += n
        logging.info(
            "%s parent=%s event=%s new_phases=%s (subs=%s)",
            games_id,
            parent_id,
            event_name,
            n,
            len(subs),
        )
        scraper.write_checkpoint(
            {
                "job": "subphases_backfill",
                "games_id": games_id,
                "parent_result_id": parent_id,
                "event_name": event_name,
                "phases_new": n,
                "phases_skipped": phases_skipped,
                "parents_scanned": scanned,
            }
        )

    summary = {
        "parents_scanned": scanned,
        "parents_with_sub_selects": parents_with_subs,
        "phases_new": phases_new,
        "phases_skipped_cached": phases_skipped,
    }
    out = Path("data/exports/olympedia_subphases_backfill.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
