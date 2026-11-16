#!/usr/bin/env python3
"""Country route of Olympedia: /countries -> each country page -> its 'Medals by Games' / participations -> /countries/<NOC>/editions/<id> (the country's Results
page for one Games) -> every /results/<id> link on it.  Everything is saved under data/raw/olympedia/countries/ and parsed into countries/country_results.json
(one row per country x edition x event x athlete).  Result ids not yet present locally are listed in countries/missing_results.json.
Resumable (cached html is reused).   Usage: python scripts/scrape_olympedia_countries.py [--delay 0.5]"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from audit_olympedia_scrape import local_ids  # noqa: E402
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS  # noqa: E402

OUT = ROOT / "data" / "raw" / "olympedia" / "countries"
H = {"User-Agent": "Mozilla/5.0 (research scraper; polite)"}
BASE = "https://www.olympedia.org"
EDS = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}
S = requests.Session()


def get(url, path, delay):
    if path.exists() and path.stat().st_size > 500:
        return path.read_text(encoding="utf-8")
    for attempt in range(6):
        try:
            r = S.get(url, headers=H, timeout=40)
        except requests.RequestException:
            time.sleep(5)
            continue
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code != 200:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text, encoding="utf-8")
        time.sleep(delay)
        return r.text
    return None


def parse_country_edition(html, noc, ed):
    s = BeautifulSoup(html, "lxml")
    rows, sport, ev = [], None, None
    for tr in s.select("table.table tr"):
        h2 = tr.select_one("h2")
        if h2:
            sport = h2.get_text(strip=True)
            continue
        td = tr.find_all("td")
        if len(td) < 4:
            continue
        a = td[0].select_one("a[href*='/results/']")
        if a:
            ev = (a.get_text(" ", strip=True), re.search(r"/results/(\d+)", a["href"]).group(1))
        ath = td[1].select_one("a[href*='/athletes/']")
        rows.append({"noc": noc, "edition_id": ed, "games_id": EDS.get(ed), "sport": sport, "event": ev[0] if ev else None, "result_id": ev[1] if ev else None,
                     "athlete": td[1].get_text(" ", strip=True), "athlete_id": re.search(r"/athletes/(\d+)", ath["href"]).group(1) if ath else None,
                     "position": td[2].get_text(" ", strip=True), "medal": td[3].get_text(" ", strip=True)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.5)
    a = ap.parse_args()
    idx = get(f"{BASE}/countries", OUT / "index.html", a.delay)
    nocs = sorted({m.group(1) for m in re.finditer(r'href="/countries/([A-Z]{2,4})"', idx)})
    print(len(nocs), "countries", flush=True)
    all_rows, pages = [], 0
    for i, noc in enumerate(nocs, 1):
        html = get(f"{BASE}/countries/{noc}", OUT / noc / "country.html", a.delay)
        if not html:
            print("fail", noc)
            continue
        eds = sorted({int(x) for x in re.findall(rf"/countries/{noc}/editions/(\d+)", html)} & set(EDS))
        for ed in eds:
            h = get(f"{BASE}/countries/{noc}/editions/{ed}", OUT / noc / f"edition_{ed}.html", a.delay)
            if h:
                pages += 1
                all_rows += parse_country_edition(h, noc, ed)
        if i % 20 == 0:
            print(f"{i}/{len(nocs)} countries, {pages} country-edition pages, {len(all_rows)} rows", flush=True)
    (OUT / "country_results.json").write_text(json.dumps(all_rows, ensure_ascii=False), encoding="utf-8")
    have = local_ids()
    miss = {}
    for r in all_rows:
        if r["result_id"] and r["result_id"] not in have:
            miss.setdefault(r["result_id"], {"id": r["result_id"], "games": r["games_id"], "select": "", "label": r["event"], "found_on": "country:" + r["noc"], "kind": "country result"})
    (OUT / "missing_results.json").write_text(json.dumps(list(miss.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: {len(nocs)} countries, {pages} country-edition pages, {len(all_rows)} rows, {len({r['result_id'] for r in all_rows if r['result_id']})} distinct results, {len(miss)} not saved locally", flush=True)


if __name__ == "__main__":
    main()
