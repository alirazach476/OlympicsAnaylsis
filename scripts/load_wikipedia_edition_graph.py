#!/usr/bin/env python3
"""Load the scraped Wikipedia edition graph (data/raw/wikipedia/edition_graph/<games_id>/{sports,countries}/*.json + edition_graph.json)
into the warehouse. Offline & idempotent (rebuilds the three wikipedia_graph_* tables from disk; raw files are never touched).

wikipedia_graph_pages  one row per sport / country page ("Swimming at the 2020 Summer Olympics", "Afghanistan at the 2020 Summer Olympics")
wikipedia_graph_tables one row per table on those pages (headers + rows as JSON)
wikipedia_graph_links  the per-edition link lists from edition_graph.json (sports, countries, ...)
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "raw" / "wikipedia" / "edition_graph"
c = sqlite3.connect(ROOT / "data" / "olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
c.executescript("""
DROP TABLE IF EXISTS wikipedia_graph_pages;
DROP TABLE IF EXISTS wikipedia_graph_tables;
DROP TABLE IF EXISTS wikipedia_graph_links;
CREATE TABLE wikipedia_graph_pages(
  page_id INTEGER PRIMARY KEY, games_id TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, url TEXT,
  infobox_json TEXT, headings_json TEXT, event_links_json TEXT, table_count INTEGER, fetched_at TEXT, raw_path TEXT,
  UNIQUE(games_id, kind, title));
CREATE TABLE wikipedia_graph_tables(
  table_id INTEGER PRIMARY KEY, page_id INTEGER NOT NULL REFERENCES wikipedia_graph_pages(page_id), games_id TEXT, kind TEXT,
  table_index INTEGER, caption TEXT, headers_json TEXT, rows_json TEXT, row_count INTEGER, truncated INTEGER);
CREATE TABLE wikipedia_graph_links(
  link_id INTEGER PRIMARY KEY, games_id TEXT NOT NULL, link_kind TEXT NOT NULL, title TEXT, url TEXT, link_text TEXT);
CREATE INDEX ix_wgp_games ON wikipedia_graph_pages(games_id, kind);
CREATE INDEX ix_wgt_page ON wikipedia_graph_tables(page_id);
CREATE INDEX ix_wgl_games ON wikipedia_graph_links(games_id, link_kind);
""")


def dumps(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else None


pages = tables = links = skipped = 0
for gdir in sorted(p for p in BASE.iterdir() if p.is_dir()):
    games_id = gdir.name
    eg = gdir / "edition_graph.json"
    if eg.exists():
        data = json.loads(eg.read_text(encoding="utf-8"))
        for key, val in data.items():
            if key.endswith("_links") and isinstance(val, list):
                for it in val:
                    if isinstance(it, dict):
                        c.execute("INSERT INTO wikipedia_graph_links(games_id,link_kind,title,url,link_text) VALUES (?,?,?,?,?)",
                                  (games_id, key[:-6], it.get("title"), it.get("url"), it.get("link_text")))
                        links += 1
    for kind, sub in (("sport", "sports"), ("country", "countries")):
        for f in sorted((gdir / sub).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                skipped += 1
                continue
            title = d.get("title") or d.get("sport_title") or f.stem.replace("_", " ")
            url = d.get("url") or "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
            tbls = d.get("tables") or []
            cur = c.execute(
                "INSERT OR REPLACE INTO wikipedia_graph_pages(games_id,kind,title,url,infobox_json,headings_json,event_links_json,table_count,fetched_at,raw_path)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (games_id, kind, title, url, dumps(d.get("infobox")), dumps(d.get("headings")), dumps(d.get("event_links")),
                 len(tbls), d.get("fetched_at"), str(f.relative_to(ROOT)).replace("\\", "/")))
            pid = cur.lastrowid
            pages += 1
            for t in tbls:
                if not isinstance(t, dict):
                    continue
                c.execute(
                    "INSERT INTO wikipedia_graph_tables(page_id,games_id,kind,table_index,caption,headers_json,rows_json,row_count,truncated)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (pid, games_id, kind, t.get("index"), t.get("caption"), dumps(t.get("headers")), dumps(t.get("rows")),
                     t.get("row_count"), 1 if t.get("truncated") else 0))
                tables += 1
c.commit()
print(f"wikipedia_graph_pages {pages} | tables {tables} | links {links} | skipped non-dict {skipped}")
