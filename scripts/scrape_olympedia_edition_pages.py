#!/usr/bin/env python3
"""Main pages of every Games on Olympedia: /editions/N (overview), /editions/N/sports/<code> (each sport's event list), /editions/N/medal, /editions/N/countries.
Saved to data/raw/olympedia/editions/<games>/main/; every /results/<id> they link is compared with the pages saved locally -> main_pages_missing.json."""
import json, re, sys, time
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from audit_olympedia_scrape import local_ids  # noqa: E402
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS  # noqa: E402
RAW = ROOT / "data/raw/olympedia/editions"
H = {"User-Agent": "Mozilla/5.0 (research scraper; polite)"}
def get(url, path):
    if path.exists() and path.stat().st_size > 500:
        return path.read_text(encoding="utf-8")
    for i in range(6):
        r = requests.get(url, headers=H, timeout=40)
        if r.status_code == 429:
            time.sleep(10 * (i + 1)); continue
        if r.status_code != 200:
            return None
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(r.text, encoding="utf-8"); time.sleep(0.4)
        return r.text
have = local_ids(); miss = {}; pages = links = 0
for games, ed in OLYMPEDIA_EDITION_IDS.items():
    d = RAW / games / "main"
    top = get(f"https://www.olympedia.org/editions/{ed}", d / "edition.html")
    if not top: print("fail", games); continue
    urls = {"medal": f"/editions/{ed}/medal", "countries": f"/editions/{ed}/countries"}
    for code in sorted(set(re.findall(rf"/editions/{ed}/sports/([A-Z0-9]+)", top))):
        urls["sport_" + code] = f"/editions/{ed}/sports/{code}"
    for name, u in urls.items():
        h = get("https://www.olympedia.org" + u, d / f"{name}.html")
        if not h: continue
        pages += 1
        for rid in set(re.findall(r"/results/(\d+)", h)):
            links += 1
            if rid not in have:
                miss.setdefault(rid, {"id": rid, "games": games, "found_on": u})
    print(games, len(urls), "pages", flush=True)
(ROOT / "data/raw/olympedia/main_pages_missing.json").write_text(json.dumps(list(miss.values()), indent=1))
print(f"{pages} main pages, {links} result links, {len(miss)} not saved locally")
