#!/usr/bin/env python3
"""Scrape ONLY the main Wikipedia article of every Games 1960-2034 (Summer + Winter). No link is followed.

For each "<year> Summer/Winter Olympics" page it stores:
  wikipedia_edition_pages     page metadata (title, url, revision id, categories, raw html path)
  wikipedia_edition_infobox   every infobox row (with its sub-header), links kept as text only
  wikipedia_edition_sections  every section's text: paragraphs, list items, image captions, references
  wikipedia_edition_tables    EVERY table on the page (wikitable, infobox-like, navbox, ...), rowspan/colspan
                              expanded, with the link targets of each cell stored as data (not visited)
Raw HTML is cached in data/raw/wikipedia_editions/. Re-runnable (replaces rows); --refresh re-downloads.
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
RAW = ROOT / "data" / "raw" / "wikipedia_editions"
DB = ROOT / "data" / "olympics_warehouse.db"
UA = {"User-Agent": "OlympicsAnalysisBot/1.0 (research project)"}

SUMMER = list(range(1960, 2036, 4))                       # 1960 ... 2032
WINTER = [1960, 1964, 1968, 1972, 1976, 1980, 1984, 1988, 1992, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026, 2030, 2034]
EDITIONS = [(f"{y}_summer", f"{y} Summer Olympics") for y in SUMMER] + [(f"{y}_winter", f"{y} Winter Olympics") for y in WINTER]

DDL = """
CREATE TABLE IF NOT EXISTS wikipedia_edition_pages (
  games_id TEXT PRIMARY KEY, title TEXT, url TEXT, page_id INTEGER, revision_id INTEGER,
  categories_json TEXT, raw_path TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS wikipedia_edition_infobox (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, ordinal INTEGER, subheader TEXT, key TEXT, value TEXT);
CREATE TABLE IF NOT EXISTS wikipedia_edition_sections (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, ordinal INTEGER, heading TEXT, level INTEGER,
  parent_heading TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS wikipedia_edition_tables (
  id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT NOT NULL, table_index INTEGER, section TEXT, caption TEXT,
  kind TEXT, n_rows INTEGER, n_cols INTEGER, headers_json TEXT, rows_json TEXT, links_json TEXT);
CREATE INDEX IF NOT EXISTS ix_wed_info ON wikipedia_edition_infobox(games_id);
CREATE INDEX IF NOT EXISTS ix_wed_sec ON wikipedia_edition_sections(games_id);
CREATE INDEX IF NOT EXISTS ix_wed_tab ON wikipedia_edition_tables(games_id);
"""


def clean(t: str) -> str:
    t = re.sub(r"\[\s*(?:\d{1,4}|[a-z]|note \d+|citation needed|clarification needed)\s*\]", "", t or "")  # [12] [a] footnote marks
    t = re.sub(r"\s+([,.;:!?)])", r"\1", t.replace("\xa0", " "))
    return re.sub(r"\s+", " ", t).strip()


def fetch(title: str, refresh: bool) -> dict:
    f = RAW / (re.sub(r"\W+", "_", title) + ".json")
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    url = ("https://en.wikipedia.org/w/api.php?action=parse&format=json&redirects=1&prop=text|categories|revid|displaytitle|sections"
           "&disableeditsection=1&page=" + up.quote(title))
    for attempt in range(6):
        try:
            data = json.loads(ur.urlopen(ur.Request(url, headers=UA), timeout=90).read().decode("utf-8"))
            break
        except Exception:  # noqa: BLE001
            time.sleep(3 * (attempt + 1))
    else:
        return {}
    if "parse" not in data:
        return {}
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(1)
    return data


def hrefs(el) -> list[str]:
    out = []
    for a in el.select("a[href]"):
        h = a["href"]
        if h.startswith("/wiki/") and ":" not in h[6:]:
            out.append(up.unquote(h[6:]).replace("_", " "))
        elif h.startswith("http"):
            out.append(h)
    return out


def expand(t):
    """Rectangular rows of (text, links) replicating rowspan/colspan cells."""
    grid, pending = [], {}
    for tr in t.select("tr"):
        if tr.find_parent("table") is not t:
            continue  # row of a nested table
        row, col = [], 0
        cells = iter([c for c in tr.find_all(["th", "td"], recursive=False)])
        while True:
            if col in pending:
                n, cell = pending[col]
                row.append(cell)
                if n > 1:
                    pending[col] = (n - 1, cell)
                else:
                    del pending[col]
                col += 1
                continue
            c = next(cells, None)
            if c is None:
                break
            for br in c.select("br"):
                br.replace_with(" / ")
            cell = (clean(c.get_text(" ")), hrefs(c))
            cs = int(re.sub(r"\D", "", c.get("colspan", "1")) or 1)
            rs = int(re.sub(r"\D", "", c.get("rowspan", "1")) or 1)
            for _ in range(cs):
                row.append(cell)
                if rs > 1:
                    pending[col] = (rs - 1, cell)
                col += 1
        while col in pending:
            n, cell = pending[col]
            row.append(cell)
            if n > 1:
                pending[col] = (n - 1, cell)
            else:
                del pending[col]
            col += 1
        if any(c[0] for c in row):
            grid.append(row)
    return grid


def table_kind(t) -> str:
    cls = " ".join(t.get("class") or [])
    for k in ("infobox", "navbox", "sidebar", "wikitable", "metadata", "ambox", "vertical-navbox"):
        if k in cls:
            return k
    return "other"


def parse(games_id: str, html: str, con):
    s = BeautifulSoup(html, "lxml")
    for x in s.select("style, script, .mw-editsection, .noprint.Inline-Template, sup.reference"):
        x.decompose()
    root = s.select_one(".mw-parser-output") or s

    # ---- infobox (every row, with its sub-header)
    ib = root.select_one("table.infobox")
    n = 0
    if ib:
        sub = None
        for tr in ib.select("tr"):
            ths, tds = tr.find_all("th", recursive=False), tr.find_all("td", recursive=False)
            if ths and not tds:
                txt = clean(ths[0].get_text(" "))
                if txt:
                    if ths[0].get("colspan"):
                        sub = txt
                    else:
                        con.execute("INSERT INTO wikipedia_edition_infobox (games_id,ordinal,subheader,key,value) VALUES (?,?,?,?,?)", (games_id, n, sub, "(title)", txt)); n += 1
            elif ths and tds:
                con.execute("INSERT INTO wikipedia_edition_infobox (games_id,ordinal,subheader,key,value) VALUES (?,?,?,?,?)",
                            (games_id, n, sub, clean(ths[0].get_text(" ")), clean(tds[0].get_text(" ")))); n += 1
            elif tds and not ths:
                txt = clean(tds[0].get_text(" "))
                if txt:
                    con.execute("INSERT INTO wikipedia_edition_infobox (games_id,ordinal,subheader,key,value) VALUES (?,?,?,?,?)", (games_id, n, sub, "(text)", txt)); n += 1

    # ---- sections: paragraphs, lists, captions, references (tables are stored separately)
    cur, lvl, parent, buf, order, secs = "Introduction", 1, None, [], 0, []
    last_h2 = None

    def flush():
        if buf:
            secs.append((cur, lvl, parent, "\n".join(buf)))

    def collect(el, out):
        if el.name in ("p", "blockquote", "dl"):
            t = clean(el.get_text(" "))
            if t:
                out.append(t)
        elif el.name in ("ul", "ol"):
            for li in el.find_all("li"):
                if li.find_parent(["ul", "ol"]) is el:
                    t = clean(li.get_text(" "))
                    if t:
                        out.append("• " + t)
        elif el.name == "figure" or "thumb" in (el.get("class") or []):
            cap = el.find(["figcaption"]) or el.select_one(".thumbcaption")
            if cap:
                t = clean(cap.get_text(" "))
                if t:
                    out.append("[Caption] " + t)
        elif el.name == "div":
            for sub in el.find_all(["p", "ul", "ol", "figcaption"], recursive=True):
                if sub.find_parent("table") is None and (sub.name != "ul" and sub.name != "ol" or sub.find_parent(["ul", "ol"]) is None):
                    if sub.name == "figcaption":
                        t = clean(sub.get_text(" "))
                        if t:
                            out.append("[Caption] " + t)
                    else:
                        collect(sub, out)

    for el in root.children:
        if not getattr(el, "name", None):
            continue
        h = el if el.name in ("h2", "h3", "h4", "h5") else (el.find(["h2", "h3", "h4", "h5"]) if "mw-heading" in (el.get("class") or []) else None)
        if h is not None:
            flush()
            cur, lvl, buf = clean(h.get_text(" ")), int(h.name[1]), []
            if lvl == 2:
                last_h2 = cur
            parent = None if lvl == 2 else last_h2
        elif el.name != "table":
            collect(el, buf)
    flush()
    for i, (h, l, p, t) in enumerate(secs):
        con.execute("INSERT INTO wikipedia_edition_sections (games_id,ordinal,heading,level,parent_heading,text) VALUES (?,?,?,?,?,?)", (games_id, i, h, l, p, t))

    # ---- every table
    nt = 0
    for ti, t in enumerate(root.select("table")):
        grid = expand(t)
        if not grid:
            continue
        h = t.find_previous(["h2", "h3", "h4", "h5"])
        cap = t.select_one("caption")
        width = max(len(r) for r in grid)
        con.execute("INSERT INTO wikipedia_edition_tables (games_id,table_index,section,caption,kind,n_rows,n_cols,headers_json,rows_json,links_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (games_id, ti, clean(h.get_text(" ")) if h else "Introduction", clean(cap.get_text(" ")) if cap else None, table_kind(t),
                     len(grid) - 1, width, json.dumps([c[0] for c in grid[0]], ensure_ascii=False),
                     json.dumps([[c[0] for c in r] for r in grid[1:]], ensure_ascii=False),
                     json.dumps([[c[1] for c in r] for r in grid[1:]], ensure_ascii=False)))
        nt += 1
    return n, len(secs), nt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--only", help="comma separated games_id list")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=120)
    con.execute("PRAGMA busy_timeout=120000")
    con.executescript(DDL)
    want = set(a.only.split(",")) if a.only else None
    for gid, title in EDITIONS:
        if want and gid not in want:
            continue
        data = fetch(title, a.refresh)
        if not data:
            print(f"{gid}: page '{title}' not found / failed", flush=True)
            continue
        p = data["parse"]
        html = p["text"]["*"]
        for t in ("wikipedia_edition_infobox", "wikipedia_edition_sections", "wikipedia_edition_tables"):
            con.execute(f"DELETE FROM {t} WHERE games_id=?", (gid,))
        ni, ns, nt = parse(gid, html, con)
        con.execute("INSERT OR REPLACE INTO wikipedia_edition_pages (games_id,title,url,page_id,revision_id,categories_json,raw_path,fetched_at) VALUES (?,?,?,?,?,?,?,?)",
                    (gid, p.get("title"), "https://en.wikipedia.org/wiki/" + p.get("title", title).replace(" ", "_"), p.get("pageid"), p.get("revid"),
                     json.dumps([c["*"] for c in p.get("categories", [])], ensure_ascii=False),
                     str(RAW / (re.sub(r"\W+", "_", title) + ".json")), datetime.now().isoformat(timespec="seconds")))
        con.commit()
        print(f"{gid}: infobox rows {ni}, sections {ns}, tables {nt}", flush=True)
    con.close()


if __name__ == "__main__":
    main()
