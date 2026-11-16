#!/usr/bin/env python3
"""Load every saved Olympedia athlete page (data/raw/olympedia_athletes/*.html) into olympedia_athlete_info - offline, no downloads (fetch_athlete_info.py would fetch ~150k pages)."""
import re, json, sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
cl = lambda t: re.sub(r"\s+", " ", t.replace("\xa0", " ").replace("•", " ")).strip()
n = 0
for f in (ROOT / "data/raw/olympedia_athletes").glob("*.html"):
    i = f.stem
    s = BeautifulSoup(f.read_text(encoding="utf-8"), "lxml"); d = {}
    for tr in s.select("table.biodata tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td: d[cl(th.get_text())] = cl(td.get_text(" "))
    g = {"Male": "Men", "Female": "Women"}.get(d.get("Sex"), "Unknown")
    m = re.search(r"\d+", d.get("Measurements", "") or "")
    c.execute("insert or replace into olympedia_athlete_info values(?,?,?,?,?,?,?,?,?,?,?,?,?)", (i, d.get("Full name") or cl((s.h1 or s).get_text()), d.get("Used name"), g, d.get("Born"), d.get("Died"), d.get("NOC"), d.get("Affiliations"), m.group(0) if m else None, None, d.get("Roles"), json.dumps(d, ensure_ascii=False), f"https://www.olympedia.org/athletes/{i}"))
    n += 1
c.commit()
print(n, "pages ->", c.execute("select count(*) from olympedia_athlete_info").fetchone()[0], "rows")
