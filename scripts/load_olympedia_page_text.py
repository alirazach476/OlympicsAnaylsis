#!/usr/bin/env python3
"""Written event descriptions and correct header facts for every saved Olympedia results page (offline, idempotent).

Reads the cached pages in data/raw/olympedia/editions/<games>/(events|phases|matches)/<result_id>.html (saved by the crawler; nothing is fetched) and stores:
  olympedia_page_text : result_id, games_id, kind, description_json (paragraphs exactly as written on Olympedia), section_meta_json (each round's own Date / Format ...), source_url
  olympedia_pages.meta_json : rewritten to the header facts only (the first fact table under the title). Before, later round tables overwrote e.g. the event Date and Format.
Usage: python scripts/load_olympedia_page_text.py"""
import json
import sqlite3
import sys
from multiprocessing import Pool
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from load_olympedia_page_tables import RAW, page_text  # noqa: E402


def one(path_s):
    p = Path(path_s)
    s = BeautifulSoup(p.read_text(encoding="utf-8", errors="replace"), "lxml")
    header, desc, smeta = page_text(s)
    return p.stem, p.parts[-3], p.parts[-2], header, desc, smeta


def main():
    files = [str(f) for g in sorted(RAW.iterdir()) if g.is_dir() for k in ("events", "phases", "matches") for f in (g / k).glob("*.html")]
    c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
    c.execute("PRAGMA busy_timeout=300000")
    c.executescript("""DROP TABLE IF EXISTS olympedia_page_text;
      CREATE TABLE olympedia_page_text (result_id TEXT PRIMARY KEY, games_id TEXT, kind TEXT, description_json TEXT, section_meta_json TEXT, source_url TEXT);""")
    n = nd = nm = 0
    with Pool(4) as pool:
        for rid, games, kind, header, desc, smeta in pool.imap_unordered(one, files, chunksize=300):
            n += 1
            if desc or smeta:
                c.execute("INSERT OR REPLACE INTO olympedia_page_text VALUES (?,?,?,?,?,?)", (rid, games, kind, json.dumps(desc, ensure_ascii=False), json.dumps(smeta, ensure_ascii=False), f"https://www.olympedia.org/results/{rid}"))
                nd += bool(desc)
            cur = c.execute("UPDATE olympedia_pages SET meta_json=? WHERE result_id=? AND meta_json IS NOT ?", (json.dumps(header, ensure_ascii=False), rid, json.dumps(header, ensure_ascii=False)))
            nm += cur.rowcount
            if n % 10000 == 0:
                c.commit(); print(n, "pages", flush=True)
    c.commit()
    ev = c.execute("SELECT COUNT(*), SUM(t.description_json IS NOT NULL AND t.description_json!='[]') FROM olympedia_pages p LEFT JOIN olympedia_page_text t USING(result_id) WHERE p.kind='events'").fetchone()
    print(f"{n:,} pages read | {nd:,} with a description | event pages with a description {ev[1]:,}/{ev[0]:,} | header facts corrected on {nm:,} pages")


if __name__ == "__main__":
    main()
