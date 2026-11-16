#!/usr/bin/env python3
"""Scrape (cached pages are reused) and load the main pages of every Games (overview, medal, countries, every sport page) plus /editions/medals and /editions/results into olympedia_site_pages / olympedia_site_tables."""
import sqlite3, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/scrape_olympedia_edition_pages.py")], check=True, env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
import crawl_olympedia_site as cs  # noqa: E402
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS as E  # noqa: E402
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
n = 0
for games, ed in E.items():
    for f in (ROOT / f"data/raw/olympedia/editions/{games}/main").glob("*.html"):
        nm = f.stem
        path = f"/editions/{ed}" if nm == "edition" else f"/editions/{ed}/{nm}" if nm in ("medal", "countries") else f"/editions/{ed}/sports/{nm[6:]}"
        cs.parse_page(c, path, f.read_text(encoding="utf-8")); n += 1
for nm in ("medals", "results"):
    p = ROOT / f"data/raw/olympedia/editions_index/{nm}.html"
    if p.exists(): cs.parse_page(c, f"/editions/{nm}", p.read_text(encoding="utf-8")); n += 1
c.commit(); print(n, "edition main pages loaded")
