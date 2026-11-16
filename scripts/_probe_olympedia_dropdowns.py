"""Probe Olympedia pages for filter/select dropdowns (phases, parts, standings)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ua = {"User-Agent": "OlympicsHistoricalCollector/1.0 (research; local-dev)"}


def show_selects(label: str, html: str) -> None:
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("h1")
    print(label, "|", title.get_text(" ", strip=True) if title else None)
    for sel in soup.select("select"):
        sid = sel.get("id") or sel.get("name") or str(sel.get("class"))
        opts = [(o.get("value"), o.get_text(" ", strip=True)) for o in sel.select("option")]
        print(f"  SELECT id={sid} n={len(opts)}")
        for v, t in opts[:25]:
            print(f"    value={v!r} text={t!r}")
        # related script
    for script in soup.select("script"):
        t = (script.get_text() or "").strip()
        if "same_games_select" in t or "other_games_select" in t or ("location.href" in t and "results" in t):
            print("  SCRIPT:", " ".join(t.split())[:400])


# 1) cached pages with selects
cached = list(Path("data/raw/olympedia/editions").glob("*/events/*.html"))
print("scan cached", len(cached))
interesting = []
for p in cached:
    text = p.read_text(encoding="utf-8", errors="replace")
    if "same_games_select" not in text and "id=\"phase" not in text:
        if text.lower().count("<select") < 1:
            continue
    soup = BeautifulSoup(text, "lxml")
    sels = soup.select("select")
    if not sels:
        continue
    # skip if only other_games_select with years
    ids = [s.get("id") for s in sels]
    if ids == ["other_games_select"]:
        continue
    interesting.append(p)
    if len(interesting) <= 6:
        show_selects(str(p), text)

print("interesting_cached", len(interesting))

# 2) Skeleton from catalogs
urls = []
for cat in Path("data/raw/olympedia/editions").glob("*/events_catalog.json"):
    for row in json.loads(cat.read_text(encoding="utf-8")):
        blob = (row.get("sport_name") or "") + " " + (row.get("event_name") or "")
        if re.search(r"Skeleton|Luge|Bobsleigh|Alpine Skiing.*Downhill", blob, re.I):
            urls.append(row["url"])
urls = list(dict.fromkeys(urls))
print("candidate urls", len(urls))
for url in urls[:5]:
    print("====", url)
    r = requests.get(url, headers=ua, timeout=60)
    print("status", r.status_code)
    if r.status_code == 200:
        show_selects(url, r.text)
        # if same_games_select has values, fetch first alternate
        soup = BeautifulSoup(r.text, "lxml")
        sel = soup.select_one("#same_games_select")
        if sel:
            vals = [o.get("value") for o in sel.select("option") if o.get("value")]
            for v in vals[:3]:
                u2 = f"https://www.olympedia.org/results/{v}"
                if u2 == url:
                    continue
                print("  -> follow dropdown", u2)
                r2 = requests.get(u2, headers=ua, timeout=60)
                if r2.status_code == 200:
                    show_selects(u2, r2.text)
