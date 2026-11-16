#!/usr/bin/env python3
"""Crawl Olympedia's site menu (Games, Countries, Sports, IOC, Statistics, Lists, ...) and team rosters.

Phase "pages":   seed menu pages + the pages they link to (countries, sports, editions, venues,
                 lists, organizations, ...). Every table is stored generically.
Phase "rosters": for every country page, every /countries/<NOC>/editions/<id> page -> who competed
                 for that NOC at that Games (athlete ids, sport, event, team, position, medal).

Everything is cached as HTML under data/raw/olympedia_site/, so re-running resumes and never
re-downloads. Tables created in data/olympics_warehouse.db:
  olympedia_site_pages   (path, title, text)
  olympedia_site_tables  (path, section, headers/rows/links as JSON)
  olympedia_rosters      (games_id, edition_id, noc, sport, event, team, athlete_id, name, position, medal)

Usage:  python scripts/crawl_olympedia_site.py [--phase pages|rosters|all] [--delay 1.0] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request as ur
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = "https://www.olympedia.org"
RAW = ROOT / "data" / "raw" / "olympedia_site"
DB = ROOT / "data" / "olympics_warehouse.db"
UA = {"User-Agent": "OlympicsAnalysisBot/1.0 (research project)"}

SEEDS = [
    "/athletes", "/athletes/doubles", "/athletes/lists", "/athletes/country_representation", "/athletes/recent_deaths",
    "/family_relations", "/counts", "/horses",
    "/countries", "/countries/best_results",
    "/editions", "/editions/medals", "/editions/results", "/ceremonies", "/venues/menu",
    "/sports", "/event_names",
    "/organizations", "/definitions", "/awards", "/meetings", "/ioc/host_cities",
    "/statistics", "/statistics/medal/country", "/statistics/medal/athlete", "/statistics/medal_table",
    "/statistics/participation", "/records", "/statistics/age", "/statistics/age_at_death",
    "/lists", "/today",
]
# pages worth following from the seeds (individual athlete / result pages are deliberately excluded)
FOLLOW = [
    r"^/lists/\d+/(manual|calculated)$", r"^/venues/\d+$", r"^/venues/[a-z_]+/\d+$",
    r"^/countries/[A-Z0-9]{2,4}$", r"^/sports/[A-Z0-9]+$", r"^/editions/\d+$",
    r"^/editions/\d+/(sports|countries|venues)$",
    r"^/organizations/\d+$", r"^/meetings/\d+$", r"^/awards/\d+$", r"^/ceremonies/\d+$",
    r"^/definitions/\d+$", r"^/ioc/[a-z_/\d]+$", r"^/records/[\w/]+$", r"^/statistics/[\w/]+$",
]

from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS  # noqa: E402

# Scope: Olympic Games 1960-2026 only (Summer + Winter). Earlier/later Games are not fetched.
SCOPE_EDITION_IDS = set(OLYMPEDIA_EDITION_IDS.values())

DDL = """
CREATE TABLE IF NOT EXISTS olympedia_site_pages (
  path TEXT PRIMARY KEY, title TEXT, text TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS olympedia_site_tables (
  id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL, section TEXT, table_index INTEGER,
  headers_json TEXT, rows_json TEXT, links_json TEXT);
CREATE INDEX IF NOT EXISTS ix_osite_tables_path ON olympedia_site_tables(path);
CREATE TABLE IF NOT EXISTS olympedia_rosters (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, edition_id INTEGER NOT NULL, noc TEXT NOT NULL,
  sport TEXT, event TEXT, event_result_id TEXT, team TEXT, athlete_id TEXT, athlete_name TEXT,
  position TEXT, medal TEXT, source_url TEXT);
CREATE INDEX IF NOT EXISTS ix_oros_ed ON olympedia_rosters(edition_id, noc);
CREATE INDEX IF NOT EXISTS ix_oros_ath ON olympedia_rosters(athlete_id);
"""


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").replace("\xa0", " ")).strip()


class Fetcher:
    def __init__(self, delay: float):
        self.delay, self.last, self.hits = delay, 0.0, 0

    def get(self, path: str) -> str | None:
        f = RAW / (re.sub(r"[^\w]+", "_", path.strip("/") or "home") + ".html")
        if f.exists() and f.stat().st_size > 200:
            return f.read_text(encoding="utf-8")
        for attempt in range(8):
            wait = self.delay - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            try:
                with ur.urlopen(ur.Request(BASE + path, headers=UA), timeout=90) as r:
                    html = r.read().decode("utf-8", errors="replace")
                self.last = time.monotonic()
                f.write_text(html, encoding="utf-8")
                self.hits += 1
                return html
            except urllib.error.HTTPError as e:
                self.last = time.monotonic()
                if e.code == 429:
                    w = min(60, 3 * 2 ** attempt)
                    print(f"  429 {path} - backing off {w}s", flush=True)
                    time.sleep(w)
                    continue
                print(f"  HTTP {e.code} {path}", flush=True)
                return None
            except Exception as e:  # noqa: BLE001
                print(f"  fetch error {path}: {e}", flush=True)
                time.sleep(min(30, 2 ** attempt))
        return None


def parse_page(con, path: str, html: str) -> BeautifulSoup:
    s = BeautifulSoup(html, "lxml")
    for n in s.select("nav, footer, script, style"):
        n.decompose()
    h1 = s.select_one("h1")
    main = s.select_one("div.container, main, body") or s
    text = "\n".join(clean(x) for x in main.get_text("\n").split("\n") if clean(x))[:200000]
    con.execute("INSERT OR REPLACE INTO olympedia_site_pages (path,title,text,fetched_at) VALUES (?,?,?,?)",
                (path, clean(h1.get_text(" ")) if h1 else None, text, datetime.now().isoformat(timespec="seconds")))
    con.execute("DELETE FROM olympedia_site_tables WHERE path=?", (path,))
    for i, t in enumerate(s.select("table")):
        h = t.find_previous(["h2", "h3"])
        rows, links = [], []
        for tr in t.select("tr"):
            cells = tr.select("th,td")
            if not cells:
                continue
            rows.append([clean(c.get_text(" ")) for c in cells])
            links.append([[a.get("href") for a in c.select("a[href]")] for c in cells])
        if rows:
            con.execute("INSERT INTO olympedia_site_tables (path,section,table_index,headers_json,rows_json,links_json) VALUES (?,?,?,?,?,?)",
                        (path, clean(h.get_text(" ")) if h else "", i, json.dumps(rows[0], ensure_ascii=False),
                         json.dumps(rows[1:], ensure_ascii=False), json.dumps(links[1:], ensure_ascii=False)))
    # every link in the page body (menus like /athletes/lists are only link lists)
    seen_l, lrows, llinks = set(), [], []
    for a in s.select("a[href]"):
        href, label = a["href"].split("#")[0], clean(a.get_text(" "))
        if href.startswith("/") and (href, label) not in seen_l and label:
            seen_l.add((href, label))
            lrows.append([label, href])
            llinks.append([[], [href]])
    if lrows:
        con.execute("INSERT INTO olympedia_site_tables (path,section,table_index,headers_json,rows_json,links_json) VALUES (?,?,?,?,?,?)",
                    (path, "__links__", -1, json.dumps(["label", "href"]), json.dumps(lrows, ensure_ascii=False), json.dumps(llinks, ensure_ascii=False)))
    return s


def internal_links(s: BeautifulSoup) -> set[str]:
    out = set()
    for a in s.select("a[href]"):
        href = a["href"].split("#")[0].split("?")[0]
        if href.startswith(BASE):
            href = href[len(BASE):]
        if href.startswith("/") and any(re.match(p, href) for p in FOLLOW):
            m = re.match(r"^/editions/(\d+)", href)
            if m and int(m.group(1)) not in SCOPE_EDITION_IDS:
                continue  # outside 1960-2026
            out.add(href)
    return out


def phase_pages(con, fx: Fetcher, limit: int | None) -> list[str]:
    queue, seen, countries = list(SEEDS), set(), []
    n = 0
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        html = fx.get(path)
        if not html:
            continue
        s = parse_page(con, path, html)
        n += 1
        con.commit()  # release the write lock after every page
        if re.match(r"^/countries/[A-Z0-9]{2,4}$", path):
            countries.append(path)
        for l in sorted(internal_links(s)):
            if l not in seen and l not in queue:
                queue.append(l)
        if n % 25 == 0:
            con.commit()
            print(f"pages: {n} done, {len(queue)} queued, last {path}", flush=True)
        if limit and n >= limit:
            break
    con.commit()
    print(f"pages phase finished: {n} pages", flush=True)
    return countries


def parse_roster(con, html: str, noc: str, edition_id: int, games_id: str | None, url: str) -> int:
    s = BeautifulSoup(html, "lxml")
    t = s.select_one("table")
    con.execute("DELETE FROM olympedia_rosters WHERE edition_id=? AND noc=?", (edition_id, noc))
    if not t:
        return 0
    sport = event = rid = team = None
    rows = 0
    for tr in t.select("tr"):
        tds = tr.select("td")
        if not tds:
            continue
        if len(tds) == 1 and tds[0].select_one("h2"):
            sport, event, rid, team = clean(tds[0].get_text(" ")), None, None, None
            continue
        c = [clean(x.get_text(" ")) for x in tds]
        ev_a = tds[0].select_one("a[href*='/results/']")
        if ev_a:
            event = clean(ev_a.get_text(" "))
            m = re.search(r"/results/(\d+)", ev_a["href"])
            rid = m.group(1) if m else None
            team = None
        elif c[0]:
            event, rid, team = c[0], None, None
        if len(tds) < 2:
            continue
        ath = tds[1].select("a[href*='/athletes/']")
        pos = c[2] if len(c) > 2 else None
        medal = c[3] if len(c) > 3 else None
        if ath:
            for a in ath:
                m = re.search(r"/athletes/(\d+)", a["href"])
                con.execute("INSERT INTO olympedia_rosters (games_id,edition_id,noc,sport,event,event_result_id,team,athlete_id,athlete_name,position,medal,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (games_id, edition_id, noc, sport, event, rid, team, m.group(1) if m else None, clean(a.get_text(" ")), pos or None, medal or None, url))
                rows += 1
        elif c[1]:  # team entry row (country/team name with the position + medal)
            team = c[1]
    return rows


def phase_rosters(con, fx: Fetcher, countries: list[str], limit: int | None) -> None:
    from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS
    by_ed = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}
    jobs = []
    for cpath in countries:
        noc = cpath.rsplit("/", 1)[1]
        row = con.execute("SELECT links_json FROM olympedia_site_tables WHERE path=? AND headers_json LIKE '%Edition%' ORDER BY table_index", (cpath,)).fetchall()
        for (lj,) in row:
            for cell_links in json.loads(lj):
                for cell in cell_links:
                    for href in cell:
                        m = re.match(rf"^/countries/{noc}/editions/(\d+)$", href)
                        if m and int(m.group(1)) in SCOPE_EDITION_IDS:
                            jobs.append((noc, int(m.group(1)), href))
    jobs = sorted(set(jobs), key=lambda j: (j[1], j[0]))
    print(f"rosters: {len(jobs)} country/edition pages to fetch", flush=True)
    done = total = 0
    for noc, eid, href in jobs:
        html = fx.get(href)
        if not html:
            continue
        total += parse_roster(con, html, noc, eid, by_ed.get(eid), BASE + href)
        con.commit()
        done += 1
        if done % 50 == 0:
            con.commit()
            print(f"rosters: {done}/{len(jobs)} pages, {total} roster rows, last {href}", flush=True)
        if limit and done >= limit:
            break
    con.commit()
    print(f"rosters phase finished: {done} pages, {total} roster rows", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["pages", "rosters", "all"], default="all")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=None, help="max pages per phase (testing)")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=120)
    con.execute("PRAGMA busy_timeout=120000")
    con.executescript(DDL)
    fx = Fetcher(a.delay)
    countries = []
    if a.phase in ("pages", "all"):
        countries = phase_pages(con, fx, a.limit)
    if a.phase in ("rosters", "all"):
        if not countries:  # resume: reuse the stored country pages
            countries = [p for (p,) in con.execute("SELECT path FROM olympedia_site_pages WHERE path GLOB '/countries/[A-Z0-9]*'") if re.match(r"^/countries/[A-Z0-9]{2,4}$", p)]
        phase_rosters(con, fx, countries, a.limit)
    con.close()
    print("DONE. new downloads this run:", fx.hits, flush=True)


if __name__ == "__main__":
    main()
