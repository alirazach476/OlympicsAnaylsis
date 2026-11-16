#!/usr/bin/env python3
"""Every saved Olympedia country page as it appears (offline): /countries/<NOC> (country page: participations, medals by Games ...) and /countries/<NOC>/editions/<id>
(the country's results at one Games: sport headings, event rows, athlete rows with place and medal).  One row per table in olympedia_country_page_tables (headers, every cell, links),
one row per page in olympedia_country_pages (title, section headings).   Usage: python scripts/load_olympedia_country_page_tables.py"""
import json, re, sqlite3, sys
from pathlib import Path
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from load_olympedia_page_tables import cell_links, cl  # noqa: E402
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS  # noqa: E402
EDS = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.executescript("""DROP TABLE IF EXISTS olympedia_country_page_tables; DROP TABLE IF EXISTS olympedia_country_pages;
  CREATE TABLE olympedia_country_pages (noc TEXT, edition_id INTEGER, games_id TEXT, page_kind TEXT, title TEXT, headings_json TEXT, source_url TEXT, PRIMARY KEY (noc, edition_id, page_kind));
  CREATE TABLE olympedia_country_page_tables (id INTEGER PRIMARY KEY, noc TEXT, edition_id INTEGER, games_id TEXT, page_kind TEXT, table_index INTEGER, section TEXT, headers_json TEXT, rows_json TEXT, links_json TEXT);""")
pages = tabs = 0
for f in sorted((ROOT / "data/raw/olympedia/countries").glob("*/*.html")):
    noc = f.parent.name
    if f.stem == "country": ed, kind, url = 0, "country", f"https://www.olympedia.org/countries/{noc}"
    else:
        ed = int(f.stem.split("_")[1]); kind, url = "country_edition", f"https://www.olympedia.org/countries/{noc}/editions/{ed}"
    s = BeautifulSoup(f.read_text(encoding="utf-8"), "lxml")
    heads = [cl(h.get_text(" ")) for h in s.select("h2,h3")]
    c.execute("INSERT OR REPLACE INTO olympedia_country_pages VALUES (?,?,?,?,?,?,?)", (noc, ed, EDS.get(ed), kind, cl(s.h1.get_text(" ")) if s.h1 else "", json.dumps(heads, ensure_ascii=False), url))
    pages += 1
    for i, t in enumerate(s.select("table")):
        cap = t.select_one("caption"); prev = t.find_previous(["h2", "h3"])
        section = cl(cap.get_text(" ")) if cap else (cl(prev.get_text(" ")) if prev else "")
        rows, links, headers, sec = [], [], None, section
        for tr in t.select("tr"):
            cells = tr.select("th,td")
            if not cells: continue
            if len(cells) == 1 and tr.select_one("h2,h3"):   # a sport heading row inside the table (as on the page)
                rows.append(["#" + cl(cells[0].get_text(" "))]); links.append([[]]); continue
            texts = [cl(x.get_text(" ")) for x in cells]
            if headers is None and not rows and all(x.name == "th" for x in cells): headers = texts; continue
            rows.append(texts); links.append([cell_links(x) for x in cells])
        if rows or headers:
            c.execute("INSERT INTO olympedia_country_page_tables (noc,edition_id,games_id,page_kind,table_index,section,headers_json,rows_json,links_json) VALUES (?,?,?,?,?,?,?,?,?)",
                      (noc, ed, EDS.get(ed), kind, i, section, json.dumps(headers, ensure_ascii=False), json.dumps(rows, ensure_ascii=False), json.dumps(links, ensure_ascii=False))); tabs += 1
c.execute("CREATE INDEX ix_ocpt ON olympedia_country_page_tables(noc, edition_id)")
c.commit(); print(pages, "country pages,", tabs, "tables")
