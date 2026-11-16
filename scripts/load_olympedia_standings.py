#!/usr/bin/env python3
"""Load scraped Olympedia standings (event + phase JSON on disk) into the warehouse.

The scraper (scrape_olympedia_results.py --no-db) only writes JSON under
data/raw/olympedia/editions/<games_id>/{events,phases}/. Nothing reads those
into the database, so this script does. It is additive: it creates the table
`olympedia_standings` and replaces rows per edition (idempotent, re-runnable).
Mojibake from the old latin-1 decoding bug is repaired on load.

Usage:
  python scripts/load_olympedia_standings.py [--winter-only|--summer-only] [--games-id 1988_winter ...]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "olympedia" / "editions"
DB = ROOT / "data" / "olympics_warehouse.db"

DDL = """
CREATE TABLE IF NOT EXISTS olympedia_standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    games_id TEXT NOT NULL,
    sport_name TEXT,
    event_name TEXT,
    parent_result_id TEXT,      -- event page id (same as result_id for the main page)
    result_id TEXT NOT NULL,    -- Olympedia /results/<id> this row came from
    is_phase INTEGER NOT NULL,  -- 0 = main event page, 1 = heat/run/round sub-page
    phase_label TEXT,
    phase_group TEXT,
    position INTEGER,
    competitor TEXT,
    noc TEXT,
    result_value TEXT,
    medal TEXT,
    extra_json TEXT,
    source_url TEXT,
    event_date TEXT,
    location TEXT
);
CREATE TABLE IF NOT EXISTS olympedia_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    games_id TEXT NOT NULL,
    sport_name TEXT,
    event_name TEXT,
    result_id TEXT NOT NULL,   -- Olympedia /results/<id> of the Match/Bout/Game page
    label TEXT,                -- e.g. "Bout #12", "Match #3"
    stage TEXT,
    match_date TEXT,
    location TEXT,
    home_team TEXT, home_noc TEXT, home_score TEXT,
    away_team TEXT, away_noc TEXT, away_score TEXT,
    period_scores TEXT,
    participants_json TEXT,    -- all competitor rows on the page (bouts)
    source_url TEXT
);
CREATE INDEX IF NOT EXISTS ix_oly_m_games ON olympedia_matches(games_id);
CREATE INDEX IF NOT EXISTS ix_oly_st_games ON olympedia_standings(games_id);
CREATE INDEX IF NOT EXISTS ix_oly_st_result ON olympedia_standings(result_id);
CREATE INDEX IF NOT EXISTS ix_oly_st_noc ON olympedia_standings(games_id, noc);
"""


def fix(s):
    """Undo UTF-8-read-as-latin-1/cp1252 double encoding; leave good text alone."""
    if not isinstance(s, str) or all(ord(c) < 128 for c in s):
        return s
    for enc in ("latin-1", "cp1252"):
        try:
            return s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return s


def fix_deep(o):
    if isinstance(o, str):
        return fix(o)
    if isinstance(o, list):
        return [fix_deep(x) for x in o]
    if isinstance(o, dict):
        return {k: fix_deep(v) for k, v in o.items()}
    return o


def rows_for(path: Path, is_phase: bool):
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta") or {}
    parent = d.get("parent_result_id") if is_phase else d.get("result_id")
    ename = d.get("parent_event_name") if is_phase else d.get("event_name")
    for s in d.get("standings") or []:
        yield (
            d["games_id"], fix(d.get("sport_name")), fix(ename), parent,
            str(d["result_id"]), int(is_phase), fix(d.get("phase_label")),
            d.get("phase_group"), s.get("position"), fix(s.get("competitor")),
            s.get("noc"), fix(s.get("result_value")), s.get("medal"),
            json.dumps({k: fix(v) for k, v in (s.get("extra") or {}).items()}, ensure_ascii=False),
            d.get("url"), fix(meta.get("date")), fix(meta.get("location")),
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-id", action="append", dest="ids")
    ap.add_argument("--winter-only", action="store_true")
    ap.add_argument("--summer-only", action="store_true")
    ap.add_argument("--db", default=str(DB))
    a = ap.parse_args()

    eds = sorted(p.name for p in RAW.iterdir() if p.is_dir())
    if a.ids:
        eds = [e for e in eds if e in a.ids]
    if a.winter_only:
        eds = [e for e in eds if e.endswith("_winter")]
    if a.summer_only:
        eds = [e for e in eds if e.endswith("_summer")]

    con = sqlite3.connect(a.db, timeout=60)
    con.executescript(DDL)
    ins = "INSERT INTO olympedia_standings (games_id,sport_name,event_name,parent_result_id,result_id,is_phase,phase_label,phase_group,position,competitor,noc,result_value,medal,extra_json,source_url,event_date,location) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    total = 0
    for g in eds:
        batch, nev, nph = [], 0, 0
        for p in sorted((RAW / g / "events").glob("*.json")):
            nev += 1
            batch.extend(rows_for(p, False))
        for p in sorted((RAW / g / "phases").glob("*.json")):
            nph += 1
            batch.extend(rows_for(p, True))
        mrows = []
        for p in sorted((RAW / g / "matches").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            parts = d.get("participants")
            mrows.append((
                g, fix(d.get("sport_name")), fix(d.get("event_name")), str(d.get("result_id")),
                fix(d.get("match_label")), fix(d.get("stage")), fix(d.get("match_date")), fix(d.get("location")),
                fix(d.get("home_team")), d.get("home_noc"), fix(d.get("home_score")),
                fix(d.get("away_team")), d.get("away_noc"), fix(d.get("away_score")),
                fix(d.get("period_scores")),
                json.dumps(fix_deep(parts), ensure_ascii=False) if parts else None, d.get("url"),
            ))
        with con:
            con.execute("DELETE FROM olympedia_standings WHERE games_id=?", (g,))
            con.executemany(ins, batch)
            con.execute("DELETE FROM olympedia_matches WHERE games_id=?", (g,))
            con.executemany("INSERT INTO olympedia_matches (games_id,sport_name,event_name,result_id,label,stage,match_date,location,home_team,home_noc,home_score,away_team,away_noc,away_score,period_scores,participants_json,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", mrows)
        total += len(batch)
        print(f"{g}: events={nev} phases={nph} rows={len(batch)} matches/bouts={len(mrows)}")
    con.close()
    print("total rows:", total)


if __name__ == "__main__":
    main()
