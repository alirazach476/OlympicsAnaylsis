#!/usr/bin/env python3
"""Fill gaps from data already on disk (no downloads).

  disciplines           <- Olympedia /sports table (olympedia_site_tables)
  events.event_gender   <- Men/Women/Mixed in the event name (only where the name says so)
  historical_nocs.flag_url / countries.flag_url <- Olympedia flag URL per NOC
  olympedia_match_players / _events / _details / _tables  <- saved Match/Bout/Game HTML pages
                         (match-day players + per-player stats, goal/card timeline, officials, venue)

Re-runnable. Usage: python scripts/enrich_offline.py [--only disciplines,gender,flags,matches]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olympics_warehouse.db"
RAW = ROOT / "data" / "raw" / "olympedia" / "editions"
FLAG = "https://olympedia-flags.s3.eu-central-1.amazonaws.com/{}.svg"

DDL = """
CREATE TABLE IF NOT EXISTS olympedia_match_players (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, team_index INTEGER, team_name TEXT,
  team_noc TEXT, position TEXT, shirt_number TEXT, player_name TEXT, athlete_id TEXT,
  is_coach INTEGER, is_team_total INTEGER, stats_json TEXT);
CREATE TABLE IF NOT EXISTS olympedia_match_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, event_time TEXT, athlete_name TEXT,
  athlete_id TEXT, noc TEXT, result TEXT, notes TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS olympedia_match_details (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, key TEXT, value TEXT);
CREATE TABLE IF NOT EXISTS olympedia_match_tables (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, table_index INTEGER, kind TEXT,
  headers_json TEXT, rows_json TEXT);
CREATE INDEX IF NOT EXISTS ix_omp_m ON olympedia_match_players(games_id, result_id);
CREATE INDEX IF NOT EXISTS ix_omp_a ON olympedia_match_players(athlete_id);
CREATE INDEX IF NOT EXISTS ix_ome_m ON olympedia_match_events(games_id, result_id);
CREATE INDEX IF NOT EXISTS ix_omd_m ON olympedia_match_details(games_id, result_id);
CREATE INDEX IF NOT EXISTS ix_omt_m ON olympedia_match_tables(games_id, result_id);
"""


def clean(t):
    return re.sub(r"\s+", " ", (t or "").replace("\xa0", " ")).strip()


def aid(cell):
    a = cell.select_one("a[href*='/athletes/']")
    m = re.search(r"/athletes/(\d+)", a["href"]) if a else None
    return m.group(1) if m else None


# ------------------------------------------------------------------ simple fills
def do_gender(con):
    n = 0
    for eid, name in con.execute("SELECT event_id, event_name FROM events WHERE event_gender IS NULL").fetchall():
        low = f" {name.lower()} "
        g = None
        if re.search(r"\b(women|woman|female|ladies)\b", low):
            g = "Women"
        elif re.search(r"\b(mixed)\b", low):
            g = "Mixed"
        elif re.search(r"\b(men|man|male|boys)\b", low):
            g = "Men"
        if g:
            con.execute("UPDATE events SET event_gender=? WHERE event_id=?", (g, eid))
            n += 1
    left = con.execute("SELECT COUNT(*) FROM events WHERE event_gender IS NULL").fetchone()[0]
    print(f"event_gender: filled {n}, still unknown {left} (name does not say)")


def do_flags(con):
    n = 0
    for code, in con.execute("SELECT noc_code FROM historical_nocs WHERE flag_url IS NULL AND noc_code IS NOT NULL").fetchall():
        con.execute("UPDATE historical_nocs SET flag_url=? WHERE noc_code=?", (FLAG.format(code), code))
        n += 1
    m = con.execute(
        "UPDATE countries SET flag_url=(SELECT h.flag_url FROM historical_nocs h WHERE h.current_country_id=countries.country_id "
        "AND h.flag_url IS NOT NULL ORDER BY COALESCE(h.valid_to_year,9999) DESC LIMIT 1) WHERE flag_url IS NULL").rowcount
    print(f"flags: historical_nocs {n}, countries {m}")


def do_disciplines(con):
    row = con.execute("SELECT rows_json FROM olympedia_site_tables WHERE path='/sports' AND section!='__links__' ORDER BY table_index LIMIT 1").fetchone()
    if not row:
        print("disciplines: /sports page not saved yet - skip")
        return
    sports = {r[1].lower(): (r[0], r[2]) for r in con.execute("SELECT sport_id, sport_name, season FROM sports")}
    con.execute("DELETE FROM disciplines")
    ins = skipped = 0
    for code, name, parent, season, *_ in json.loads(row[0]):
        hit = sports.get(name.lower()) or sports.get(parent.lower())
        if not hit:
            skipped += 1
            continue
        con.execute("INSERT INTO disciplines (sport_id, discipline_name, season, source_url, verification_status) VALUES (?,?,?,?,?)",
                    (hit[0], name, (season or "").lower() or None, "https://www.olympedia.org/sports", "collected"))
        ins += 1
    print(f"disciplines: inserted {ins}, no matching sport for {skipped}")


# ------------------------------------------------------------------ match pages
def parse_match(games_id, rid, html):
    s = BeautifulSoup(html, "lxml")
    details, players, events, tables = [], [], [], []
    for tr in s.select("table.biodata tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td:
            details.append((clean(th.get_text(" ")), clean(td.get_text(" "))))
    team_names = []
    team_idx = 0
    for ti, t in enumerate(s.select("table")):
        if "biodata" in (t.get("class") or []):
            continue
        trs = t.select("tr")
        if not trs:
            continue
        hdr = [clean(c.get_text(" ")) for c in trs[0].select("th,td")]
        body = [[(clean(c.get_text(" ")), aid(c)) for c in tr.select("th,td")] for tr in trs[1:]]
        low = [h.lower() for h in hdr]
        if low[:2] == ["time", "athlete(s)"]:
            kind = "events"
            for r in body:
                d = {hdr[i] if i < len(hdr) and hdr[i] else f"col{i}": r[i][0] for i in range(len(r))}
                events.append((r[0][0] if r else None, r[1][0] if len(r) > 1 else None, r[1][1] if len(r) > 1 else None,
                               d.get("NOC"), d.get("Result"), d.get("Notes"), json.dumps(d, ensure_ascii=False)))
        elif "pos" in low and "competitor" in low:
            kind = "players"
            team_idx += 1
            tname = team_names[team_idx - 1][0] if len(team_names) >= team_idx else None
            tnoc = team_names[team_idx - 1][1] if len(team_names) >= team_idx else None
            ip, inum, ic = low.index("pos"), (low.index("number") if "number" in low else None), low.index("competitor")
            for r in body:
                if not r:
                    continue
                first = r[0][0]
                stats = {hdr[i]: r[i][0] for i in range(len(r)) if i < len(hdr) and hdr[i] and i not in (ip, inum, ic) and r[i][0]}
                if first.lower() == "coach":
                    players.append((team_idx, tname, tnoc, "Coach", None, r[1][0] if len(r) > 1 else None, r[1][1] if len(r) > 1 else None, 1, 0, "{}"))
                elif first.lower().startswith("team total"):
                    players.append((team_idx, tname, tnoc, "Team Totals", None, None, None, 0, 1, json.dumps(stats, ensure_ascii=False)))
                else:
                    players.append((team_idx, tname, tnoc, first, r[inum][0] if inum is not None and inum < len(r) else None,
                                    r[ic][0] if ic < len(r) else None, r[ic][1] if ic < len(r) else None, 0, 0, json.dumps(stats, ensure_ascii=False)))
        else:
            kind = "scoreboard" if ("competitor" in low or "team" in low) and "noc" in low and len(body) <= 4 else "other"
            if kind == "scoreboard" and not team_names:
                ic = low.index("competitor") if "competitor" in low else low.index("team")
                inoc = low.index("noc")
                team_names = [(r[ic][0], r[inoc][0] if inoc < len(r) else None) for r in body if len(r) > ic]
        tables.append((ti, kind, json.dumps(hdr, ensure_ascii=False), json.dumps([[c[0] for c in r] for r in body], ensure_ascii=False)))
    return details, players, events, tables


def do_matches(con):
    con.executescript(DDL)
    con.execute("CREATE TABLE IF NOT EXISTS olympedia_match_done (games_id TEXT PRIMARY KEY, pages INTEGER)")
    con.commit()
    done = {r[0] for r in con.execute("SELECT games_id FROM olympedia_match_done")}
    for ed in sorted(p.name for p in RAW.iterdir() if p.is_dir()):
        files = sorted((RAW / ed / "matches").glob("*.html"))
        if not files:
            continue
        if ed in done:
            print(f"matches {ed}: already loaded, skip")
            continue
        for t in ("olympedia_match_players", "olympedia_match_events", "olympedia_match_details", "olympedia_match_tables"):
            con.execute(f"DELETE FROM {t} WHERE games_id=?", (ed,))  # drop any partial earlier run
        con.commit()
        np = ne = nd = 0
        for k, f in enumerate(files, 1):
            rid = f.stem
            details, players, events, tables = parse_match(ed, rid, f.read_text(encoding="utf-8", errors="replace"))
            con.executemany("INSERT INTO olympedia_match_details (games_id,result_id,key,value) VALUES (?,?,?,?)", [(ed, rid, k2, v) for k2, v in details])
            con.executemany("INSERT INTO olympedia_match_players (games_id,result_id,team_index,team_name,team_noc,position,shirt_number,player_name,athlete_id,is_coach,is_team_total,stats_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            [(ed, rid) + p for p in players])
            con.executemany("INSERT INTO olympedia_match_events (games_id,result_id,event_time,athlete_name,athlete_id,noc,result,notes,raw_json) VALUES (?,?,?,?,?,?,?,?,?)",
                            [(ed, rid) + e for e in events])
            con.executemany("INSERT INTO olympedia_match_tables (games_id,result_id,table_index,kind,headers_json,rows_json) VALUES (?,?,?,?,?,?)",
                            [(ed, rid) + t for t in tables])
            np, ne, nd = np + len(players), ne + len(events), nd + len(details)
            if k % 300 == 0:
                con.commit()  # short write locks so the scrapers are never blocked
        con.execute("INSERT OR REPLACE INTO olympedia_match_done (games_id, pages) VALUES (?,?)", (ed, len(files)))
        con.commit()
        print(f"matches {ed}: {len(files)} pages -> players {np}, events {ne}, details {nd}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="gender,flags,disciplines,matches")
    a = ap.parse_args()
    con = sqlite3.connect(DB, timeout=120)
    con.execute("PRAGMA busy_timeout=120000")
    for step in a.only.split(","):
        {"gender": do_gender, "flags": do_flags, "disciplines": do_disciplines, "matches": do_matches}[step](con)
        con.commit()
    con.close()


if __name__ == "__main__":
    main()
