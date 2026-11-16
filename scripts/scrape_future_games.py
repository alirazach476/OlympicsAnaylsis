#!/usr/bin/env python3
"""Scrape upcoming Games (2028/2032 Summer, 2030/2034 Winter) from Wikipedia + Olympedia.

No rosters. Saves raw HTML under data/raw/future_games/ (cached) and loads:
  games                  one row per future Games, verification_status='planned'
  venues                 planned venues (verification_status='planned')
  future_games_facts     infobox / Olympedia summary key-values
  future_games_sections  full text of every article section
  future_games_tables    every wikitable on every page (headers + rows as JSON)
  future_games_links     source pages used
Re-runnable: replaces rows for these four games each time (--refresh re-downloads).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import urllib.parse as up
import urllib.request as ur
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "future_games"
DB = ROOT / "data" / "olympics_warehouse.db"
UA = {"User-Agent": "OlympicsAnalysisBot/1.0 (research project)"}

GAMES = {
    "2028_summer": dict(year=2028, season="summer", edition=34, name="Games of the XXXIV Olympiad", olympedia=64,
                        wiki=["2028 Summer Olympics", "Venues of the 2028 Summer Olympics and Paralympics",
                              "Baseball at the 2028 Summer Olympics", "Cricket at the 2028 Summer Olympics",
                              "Flag football at the 2028 Summer Olympics", "Squash at the 2028 Summer Olympics"]),
    "2032_summer": dict(year=2032, season="summer", edition=35, name="Games of the XXXV Olympiad", olympedia=372,
                        wiki=["2032 Summer Olympics", "Venues of the 2032 Summer Olympics and Paralympics",
                              "Bids for the 2032 Summer Olympics", "Brisbane bid for the 2032 Summer Olympics"]),
    "2030_winter": dict(year=2030, season="winter", edition=26, name="XXVI Olympic Winter Games", olympedia=373,
                        wiki=["2030 Winter Olympics", "Bids for the 2030 Winter Olympics"]),
    "2034_winter": dict(year=2034, season="winter", edition=27, name="XXVII Olympic Winter Games", olympedia=374,
                        wiki=["2034 Winter Olympics", "Bids for the 2034 Winter Olympics",
                              "Salt Lake City bids for the Winter Olympics"]),
}

DDL = """
CREATE TABLE IF NOT EXISTS future_games_facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, source TEXT, page TEXT, key TEXT, value TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS future_games_sections (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, page TEXT, heading TEXT, level INTEGER, text TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS future_games_tables (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, page TEXT, section TEXT, table_index INTEGER,
  caption TEXT, headers_json TEXT, rows_json TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS future_games_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, source TEXT, page TEXT, url TEXT, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_fg_facts ON future_games_facts(games_id);
CREATE INDEX IF NOT EXISTS ix_fg_sections ON future_games_sections(games_id);
CREATE INDEX IF NOT EXISTS ix_fg_tables ON future_games_tables(games_id);
"""


def clean(t: str) -> str:
    t = re.sub(r"\[\s*[^\]]{0,12}\s*\]", "", t or "")  # [ 12 ] [a] [citation needed]
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def http(url: str) -> str:
    for attempt in range(5):
        try:
            return ur.urlopen(ur.Request(url, headers=UA), timeout=60).read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
            last = e
    raise last


def wiki_html(title: str, refresh: bool) -> str | None:
    f = RAW / ("wiki_" + re.sub(r"\W+", "_", title) + ".html")
    if f.exists() and not refresh:
        return f.read_text(encoding="utf-8")
    try:
        j = json.loads(http("https://en.wikipedia.org/w/api.php?action=parse&prop=text&format=json&redirects=1&page=" + up.quote(title)))
        html = j["parse"]["text"]["*"]
    except Exception:  # noqa: BLE001
        return None
    f.write_text(html, encoding="utf-8")
    time.sleep(1)
    return html


def oly_html(eid: int, sub: str, refresh: bool) -> str | None:
    f = RAW / f"olympedia_{eid}{sub.replace('/', '_')}.html"
    if f.exists() and not refresh:
        return f.read_text(encoding="utf-8")
    try:
        html = http(f"https://www.olympedia.org/editions/{eid}{sub}")
    except Exception:  # noqa: BLE001
        return None
    f.write_text(html, encoding="utf-8")
    time.sleep(1)
    return html


def parse_date(s: str):
    s = clean(s)
    for fmt in ("%B %d, %Y", "%d %B %Y", "%B %d %Y"):
        m = re.match(r"([A-Za-z]+ \d{1,2},? \d{4}|\d{1,2} [A-Za-z]+ \d{4})", s)
        if m:
            try:
                return datetime.strptime(m.group(1).replace(",", ""), fmt.replace(",", "")).date().isoformat()
            except ValueError:
                continue
    return None


def infobox(soup):
    out = {}
    ib = soup.select_one("table.infobox")
    if not ib:
        return out
    for tr in ib.select("tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td:
            out[clean(th.get_text(" "))] = clean(td.get_text(" "))
    return out


def sections(soup):
    root = soup.select_one(".mw-parser-output") or soup
    cur, lvl, buf, out = "Introduction", 1, [], []
    for el in root.children:
        if not getattr(el, "name", None):
            continue
        h = el if el.name in ("h2", "h3", "h4") else el.find(["h2", "h3", "h4"]) if "mw-heading" in (el.get("class") or []) else None
        if h is not None:
            if buf:
                out.append((cur, lvl, "\n".join(buf)))
            cur, lvl, buf = clean(h.get_text(" ")), int(h.name[1]), []
        elif el.name in ("p", "ul", "ol", "dl"):
            t = clean(el.get_text(" "))
            if t:
                buf.append(t)
    if buf:
        out.append((cur, lvl, "\n".join(buf)))
    return out


def expand(t):
    """Table -> rectangular rows, replicating rowspan/colspan cells."""
    grid, pending = [], {}  # pending[col] = (remaining_rows, text)
    for tr in t.select("tr"):
        row, col = [], 0
        cells = iter(tr.select("th,td"))
        while True:
            if col in pending:
                n, txt = pending[col]
                row.append(txt)
                pending[col] = (n - 1, txt) if n > 1 else None
                if pending[col] is None:
                    del pending[col]
                col += 1
                continue
            c = next(cells, None)
            if c is None:
                break
            txt = clean(c.get_text(" "))
            cs = int(re.sub(r"\D", "", c.get("colspan", "1")) or 1)
            rs = int(re.sub(r"\D", "", c.get("rowspan", "1")) or 1)
            for _ in range(cs):
                row.append(txt)
                if rs > 1:
                    pending[col] = (rs - 1, txt)
                col += 1
        while col in pending:  # trailing spanned cells
            n, txt = pending[col]
            row.append(txt)
            pending[col] = (n - 1, txt) if n > 1 else None
            if pending[col] is None:
                del pending[col]
            col += 1
        if any(row):
            grid.append(row)
    return grid


def tables(soup):
    out = []
    for i, t in enumerate(soup.select("table.wikitable")):
        h = t.find_previous(["h2", "h3", "h4"])
        cap = t.select_one("caption")
        rows = expand(t)
        if not rows:
            continue
        out.append((clean(h.get_text(" ")) if h else "", i, clean(cap.get_text(" ")) if cap else "", rows[0], rows[1:]))
    return out


def venues_from(table):
    """(venue, events, capacity, status, location) from a table that has a Venue column."""
    sec, _, cap, hdr, rows = table
    low = [re.sub(r"\s*\[.*", "", h).lower() for h in hdr]
    if not any(h.startswith("venue") for h in low):
        return []
    ix = lambda *names: next((i for i, h in enumerate(low) if any(h.startswith(n) for n in names)), None)  # noqa: E731
    iv, ie, ic, il = ix("venue"), ix("olympic events", "events", "event", "sport"), ix("capacity"), ix("suburb", "location", "city")
    res = []
    for r in rows:
        extra = len(r) - len(hdr)
        if extra > 0 and iv is not None:  # venue complex + sub-venue spread over extra leading columns
            r = [" / ".join(dict.fromkeys(r[: extra + 1]))] + r[extra + 1:]
        if iv is None or iv >= len(r) or not r[iv]:
            continue
        capacity = None
        if ic is not None and ic < len(r):
            m = re.search(r"\d[\d,]*", r[ic])
            capacity = float(m.group(0).replace(",", "")) if m else None
        res.append((r[iv], r[ie] if ie is not None and ie < len(r) else None, capacity,
                    r[il] if il is not None and il < len(r) else None, sec))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=60)
    con.executescript(DDL)
    now = datetime.now().isoformat(timespec="seconds")

    for gid, g in GAMES.items():
        for tbl in ("future_games_facts", "future_games_sections", "future_games_tables", "future_games_links"):
            con.execute(f"DELETE FROM {tbl} WHERE games_id=?", (gid,))
        con.execute("DELETE FROM venues WHERE games_id=?", (gid,))
        main_ib, venue_rows = {}, []

        for title in g["wiki"]:
            html = wiki_html(title, a.refresh)
            if not html:
                print(f"  {gid}: wikipedia page not found: {title}")
                continue
            url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
            soup = BeautifulSoup(html, "lxml")
            con.execute("INSERT INTO future_games_links (games_id,source,page,url,fetched_at) VALUES (?,?,?,?,?)", (gid, "wikipedia", title, url, now))
            ib = infobox(soup)
            if title == g["wiki"][0]:
                main_ib = ib
            for k, v in ib.items():
                con.execute("INSERT INTO future_games_facts (games_id,source,page,key,value,source_url) VALUES (?,?,?,?,?,?)", (gid, "wikipedia", title, k, v, url))
            for h, lvl, txt in sections(soup):
                con.execute("INSERT INTO future_games_sections (games_id,page,heading,level,text,source_url) VALUES (?,?,?,?,?,?)", (gid, title, h, lvl, txt, url))
            for tb in tables(soup):
                con.execute("INSERT INTO future_games_tables (games_id,page,section,table_index,caption,headers_json,rows_json,source_url) VALUES (?,?,?,?,?,?,?,?)",
                            (gid, title, tb[0], tb[1], tb[2], json.dumps(tb[3], ensure_ascii=False), json.dumps(tb[4], ensure_ascii=False), url))
                if "Venues of the" in title or title == g["wiki"][0]:
                    venue_rows += [(v, url) for v in venues_from(tb)]

        # Olympedia summary + sub pages
        oly_url = f"https://www.olympedia.org/editions/{g['olympedia']}"
        oly_facts = {}
        for sub in ("", "/countries", "/result"):
            html = oly_html(g["olympedia"], sub, a.refresh)
            if not html:
                continue
            con.execute("INSERT INTO future_games_links (games_id,source,page,url,fetched_at) VALUES (?,?,?,?,?)", (gid, "olympedia", sub or "/", oly_url + sub, now))
            soup = BeautifulSoup(html, "lxml")
            for tr in (soup.select("table.biodata tr") or soup.select("table tr")[:12] if sub == "" else soup.select("table.biodata tr")):
                th, td = tr.select_one("th"), tr.select_one("td")
                if th and td:
                    k, v = clean(th.get_text(" ")), clean(td.get_text(" "))
                    oly_facts[k] = v
                    con.execute("INSERT INTO future_games_facts (games_id,source,page,key,value,source_url) VALUES (?,?,?,?,?,?)", (gid, "olympedia", sub or "/", k, v, oly_url + sub))
            for ti, t in enumerate(soup.select("table")):
                rows = [[clean(c.get_text(" ")) for c in tr.select("th,td")] for tr in t.select("tr")]
                rows = [r for r in rows if any(r)]
                if rows:
                    con.execute("INSERT INTO future_games_tables (games_id,page,section,table_index,caption,headers_json,rows_json,source_url) VALUES (?,?,?,?,?,?,?,?)",
                                (gid, "olympedia" + (sub or "/"), "", ti, "", json.dumps(rows[0], ensure_ascii=False), json.dumps(rows[1:], ensure_ascii=False), oly_url + sub))

        # games row
        host = clean(main_ib.get("Location", "")).replace(" ,", ",")
        # Host city/country from the IOC host-election result (Wikipedia vote tables / "Winner" fact)
        HOSTS = {"2028_summer": ("Los Angeles", "United States"), "2032_summer": ("Brisbane", "Australia"),
                 "2030_winter": ("French Alps", "France"), "2034_winter": ("Salt Lake City", "United States")}
        city, country = HOSTS[gid]
        ev = re.search(r"(\d+)\s+in\s+(\d+)\s+sports", main_ib.get("Events", ""))
        opening, closing = parse_date(main_ib.get("Opening", "")), parse_date(main_ib.get("Closing", ""))
        con.execute("DELETE FROM games WHERE games_id=?", (gid,))
        con.execute(
            "INSERT INTO games (games_id,year,season,official_edition_name,edition_number,host_city,host_country,opening_date,closing_date,"
            "actual_event_start_date,actual_event_end_date,total_sports,total_events,wikipedia_url,olympedia_url,source,verification_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, g["year"], g["season"], g["name"], g["edition"], city, country, opening, closing, opening, closing,
             int(ev.group(2)) if ev else None, int(ev.group(1)) if ev else None,
             "https://en.wikipedia.org/wiki/" + g["wiki"][0].replace(" ", "_"), oly_url,
             "wikipedia+olympedia (future games, planned)", "planned", now, now),
        )
        seen = set()
        for (v, ev_txt, cap, loc, sec), url in venue_rows:
            if (v, ev_txt) in seen:
                continue
            seen.add((v, ev_txt))
            con.execute("INSERT INTO venues (games_id,venue_name,city,country,sport,capacity,source_url,verification_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (gid, v, loc or sec, None, ev_txt, cap, url, "planned", now, now))
        con.commit()
        n = lambda t: con.execute(f"SELECT COUNT(*) FROM {t} WHERE games_id=?", (gid,)).fetchone()[0]  # noqa: E731
        print(f"{gid}: host={host!r} open={opening} close={closing} events={ev.group(1) if ev else None} sports={ev.group(2) if ev else None} "
              f"| facts={n('future_games_facts')} sections={n('future_games_sections')} tables={n('future_games_tables')} venues={n('venues')}")
    con.close()


if __name__ == "__main__":
    main()
