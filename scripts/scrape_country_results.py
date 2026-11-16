#!/usr/bin/env python3
"""Olympedia: Medals-by-country -> every country -> its "Results" link per Games (1960-2026 only).

Path followed (nothing else):
  /statistics/medal/country                 -> olympedia_country_medals (gold/silver/bronze per country)
    -> /countries/<NOC>                     -> olympedia_country_participation (men/women/total per Games)
      -> "Results" link /countries/<NOC>/editions/<id>   (only the 35 Games 1960 Summer .. 2026 Winter)
                                            -> olympedia_rosters (every athlete/team entry: sport, event, team,
                                               position, medal, athlete id)

Resumable: HTML is cached in data/raw/olympedia_site/, rows are saved after every page, and finished
country/Games pages are skipped. Usage: python scripts/scrape_country_results.py [--delay 1.0] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from crawl_olympedia_site import (  # noqa: E402
    DB, DDL, SCOPE_EDITION_IDS, Fetcher, clean, parse_page, parse_roster,
)
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS  # noqa: E402

EXTRA_DDL = """
CREATE TABLE IF NOT EXISTS olympedia_country_medals (
  noc TEXT PRIMARY KEY, country TEXT, gold INTEGER, silver INTEGER, bronze INTEGER, total INTEGER, source_url TEXT);
CREATE TABLE IF NOT EXISTS olympedia_country_participation (
  id INTEGER PRIMARY KEY AUTOINCREMENT, noc TEXT, edition_id INTEGER, games_id TEXT, edition_label TEXT,
  represented_as TEXT, men INTEGER, women INTEGER, total INTEGER, results_url TEXT);
CREATE INDEX IF NOT EXISTS ix_ocp_noc ON olympedia_country_participation(noc);
CREATE TABLE IF NOT EXISTS olympedia_country_results_done (
  noc TEXT, edition_id INTEGER, rows INTEGER, PRIMARY KEY (noc, edition_id));
"""


def to_int(s):
    m = re.search(r"-?\d+", (s or "").replace(",", ""))
    return int(m.group(0)) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=None, help="max Results pages (testing)")
    a = ap.parse_args()
    by_ed = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}
    con = sqlite3.connect(DB, timeout=120)
    con.execute("PRAGMA busy_timeout=120000")
    con.executescript(DDL + EXTRA_DDL)
    fx = Fetcher(a.delay)

    # 1) medals by country -> list of country links
    html = fx.get("/statistics/medal/country")
    s = parse_page(con, "/statistics/medal/country", html)
    countries = []
    for tr in s.select("table tr")[1:]:
        tds = tr.select("td")
        if len(tds) < 6:
            continue
        link = tds[0].select_one("a[href^='/countries/']")
        if not link:
            continue
        noc = link["href"].rsplit("/", 1)[1]
        con.execute("INSERT OR REPLACE INTO olympedia_country_medals VALUES (?,?,?,?,?,?,?)",
                    (noc, clean(tds[0].get_text(" ")), to_int(tds[2].get_text()), to_int(tds[3].get_text()),
                     to_int(tds[4].get_text()), to_int(tds[5].get_text()), "https://www.olympedia.org/statistics/medal/country"))
        countries.append((noc, link["href"]))
    con.commit()
    print(f"medal page: {len(countries)} countries", flush=True)

    # 2) every country page -> its Results links for 1960-2026
    jobs = []
    for noc, href in countries:
        html = fx.get(href)
        if not html:
            print(f"  could not fetch {href}", flush=True)
            continue
        cs = BeautifulSoup(html, "lxml")
        parse_page(con, href, html)
        con.execute("DELETE FROM olympedia_country_participation WHERE noc=?", (noc,))
        for tr in cs.select("table tr"):
            tds = tr.select("td")
            if len(tds) < 6:
                continue
            res = tr.select_one(f"a[href^='/countries/{noc}/editions/']")
            ed = tr.select_one("a[href^='/editions/']")
            if not (res and ed):
                continue
            eid = int(re.search(r"/editions/(\d+)", ed["href"]).group(1))
            if eid not in SCOPE_EDITION_IDS:
                continue  # outside 1960-2026
            con.execute("INSERT INTO olympedia_country_participation (noc,edition_id,games_id,edition_label,represented_as,men,women,total,results_url) VALUES (?,?,?,?,?,?,?,?,?)",
                        (noc, eid, by_ed.get(eid), clean(tds[0].get_text(" ")), clean(tds[1].get_text(" ")), to_int(tds[2].get_text()),
                         to_int(tds[3].get_text()), to_int(tds[4].get_text()), "https://www.olympedia.org" + res["href"]))
            jobs.append((noc, eid, res["href"]))
        con.commit()
    jobs = sorted(set(jobs), key=lambda j: (j[1], j[0]))
    done = {(r[0], r[1]) for r in con.execute("SELECT noc, edition_id FROM olympedia_country_results_done")}
    todo = [j for j in jobs if (j[0], j[1]) not in done]
    print(f"{len(jobs)} Results pages for 1960-2026 across {len(countries)} countries ({len(todo)} still to fetch)", flush=True)

    # 3) every Results page
    n = rows_total = 0
    for noc, eid, href in todo:
        html = fx.get(href)
        if not html:
            continue
        k = parse_roster(con, html, noc, eid, by_ed.get(eid), "https://www.olympedia.org" + href)
        con.execute("INSERT OR REPLACE INTO olympedia_country_results_done VALUES (?,?,?)", (noc, eid, k))
        con.commit()
        n, rows_total = n + 1, rows_total + k
        if n % 50 == 0:
            print(f"results: {n}/{len(todo)} pages, {rows_total} rows, last {href}", flush=True)
        if a.limit and n >= a.limit:
            break
    print(f"FINISHED: {n} Results pages, {rows_total} roster/result rows", flush=True)


if __name__ == "__main__":
    main()
