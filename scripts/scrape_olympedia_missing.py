#!/usr/bin/env python3
"""Scrape the Olympedia pages that the audit (scripts/audit_olympedia_scrape.py) found missing, one page at a time (polite, resumable).

The original scraper followed only links labelled match / bout / game / tie-break / replay from EVENT pages and never followed links found on dropdown (phase)
pages, so Bout 1/2, Bout 3/4, Play-Off, Barrage, Final ... pages and some run dropdown options (e.g. weightlifting 'Lift #n') were skipped. This script:
  * fetches every missing page (rate-limit aware: backs off on HTTP 429) into editions/<games_id>/pending/<id>.html
  * keeps it only if the page belongs to the SAME Games (edition id in its breadcrumb); references to earlier Games (1956, 1952 ...) are out of scope and dropped
  * classifies it: a match / bout page (two competitors) -> matches/<id>.{html,json} in the MatchFixture format; anything else -> phases/<id>.{html,json}
  * scans every newly saved page for further results links / dropdown options and queues them, until nothing in scope is missing
State is kept in data/raw/olympedia/scrape_missing_state.json, so it can be stopped and restarted.   Usage: python scripts/scrape_olympedia_missing.py [--delay 1.0] [--limit N]"""
import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from audit_olympedia_scrape import local_ids, scan  # noqa: E402
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS  # noqa: E402
from backend.scrapers.olympedia.results import OlympediaResultsScraper  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scrape_missing")
RAW = ROOT / "data" / "raw" / "olympedia"
EDITIONS = RAW / "editions"
STATE = RAW / "scrape_missing_state.json"
HISTORICAL = re.compile(r"\b(18|19|20)\d\d\b|olympics|melbourne|helsinki|berlin|london|this (event|class)|medalist|champion|in australia|in finland", re.I)
MATCH_LABEL = re.compile(r"(?i)\b(match|bout|game|play-?off|barrage|tie-?break|replay|duel)\b")
EDITION_TO_GAMES = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"done": {}, "out_of_scope": {}, "failed": {}}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def parent_info(games, found_on):
    for kind in ("events", "phases", "matches"):
        p = EDITIONS / games / kind / f"{found_on}.json"
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            return d.get("sport_name") or "Unknown", d.get("event_name") or d.get("parent_event_name") or found_on, kind, d
    return "Unknown", found_on, "events", {}


def page_edition(html):
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("ol.breadcrumb a[href*='/editions/'], .breadcrumb a[href*='/editions/']"):
        m = re.search(r"/editions/(\d+)", a.get("href") or "")
        if m:
            return int(m.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--games-id", action="append", dest="games_ids")
    args = ap.parse_args()

    scraper = OlympediaResultsScraper(session=None, delay=args.delay)
    st = load_state()
    have = local_ids()
    work = json.loads((RAW / "missing_pages.json").read_text(encoding="utf-8"))
    queue = []
    for w in work:
        if w["id"] in have or w["id"] in st["done"] or w["id"] in st["out_of_scope"]:
            continue
        if w["kind"] == "page link" and HISTORICAL.search(w["label"] or ""):
            st["out_of_scope"][w["id"]] = "historical reference: " + (w["label"] or "")
            continue
        if args.games_ids and w["games"] not in args.games_ids:
            continue
        queue.append(w)
    log.info("%s pages to fetch (%s already done, %s out of scope so far)", len(queue), len(st["done"]), len(st["out_of_scope"]))
    n = 0
    t0 = time.time()
    seen = {w["id"] for w in queue}
    while queue and (args.limit is None or n < args.limit):
        w = queue.pop(0)
        rid, games, label = w["id"], w["games"], w["label"] or ""
        if rid in have or rid in st["done"] or rid in st["out_of_scope"]:
            continue
        url = f"https://www.olympedia.org/results/{rid}"
        pend = f"editions/{games}/pending/{rid}.html"
        html = scraper.fetch_html(url, pend)
        n += 1
        if not html:
            st["failed"][rid] = {"games": games, "label": label, "url": url}
            continue
        ed = page_edition(html)
        if ed is not None and EDITION_TO_GAMES.get(ed) != games:
            st["out_of_scope"][rid] = f"edition {ed} is not {games}: {label}"
            (RAW / pend).unlink(missing_ok=True)
            continue
        sport, event, pkind, pdata = parent_info(games, w["found_on"])
        standings, nested, meta = scraper.parse_event_page(html)
        is_match = bool(MATCH_LABEL.search(label)) or (re.search(r"(?i)\bfinal\b", label) is not None and len(standings) <= 2)
        gdir = EDITIONS / games
        if is_match:
            fx = scraper.parse_match_page(games, sport, event, label, rid, url, html)
            try:
                fx.participants = [asdict(r) for r in standings]
            except Exception:  # noqa: BLE001
                fx.participants = None
            (gdir / "matches").mkdir(parents=True, exist_ok=True)
            (gdir / "matches" / f"{rid}.html").write_text(html, encoding="utf-8")
            (gdir / "matches" / f"{rid}.json").write_text(json.dumps(asdict(fx), ensure_ascii=False, indent=2), encoding="utf-8")
            kind, target = "match", gdir / "matches" / f"{rid}.html"
        else:
            out = {"games_id": games, "parent_result_id": w["found_on"], "parent_event_name": event, "sport_name": sport, "phase_label": label, "phase_group": w.get("select") or "linked",
                   "select_id": w.get("select") or "link", "result_id": rid, "url": url, "meta": meta, "standings": [asdict(s) for s in standings],
                   "nested_links": [{"label": a, "url": b} for a, b in nested], "sub_select_links": scraper.parse_sub_selects(html), "scraped_at": datetime.now(timezone.utc).isoformat()}
            (gdir / "phases").mkdir(parents=True, exist_ok=True)
            (gdir / "phases" / f"{rid}.html").write_text(html, encoding="utf-8")
            (gdir / "phases" / f"{rid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            kind, target = "phase", gdir / "phases" / f"{rid}.html"
        (RAW / pend).unlink(missing_ok=True)
        have[rid] = (games, "matches" if kind == "match" else "phases")
        st["done"][rid] = {"games": games, "kind": kind, "label": label}
        # follow whatever this page itself links to (closure): same-Games match / phase pages not yet saved
        try:
            r = scan(str(target))
            for sid, v, lab in r["options"]:
                if v not in have and v not in seen and v not in st["out_of_scope"]:
                    seen.add(v)
                    queue.append({"id": v, "games": games, "select": re.sub(r"\d+", "N", sid), "label": lab, "found_on": rid, "kind": "dropdown option"})
            for v, lab in r["links"]:
                if v not in have and v not in seen and v not in st["out_of_scope"] and not HISTORICAL.search(lab or ""):
                    seen.add(v)
                    queue.append({"id": v, "games": games, "select": "", "label": lab, "found_on": rid, "kind": "page link"})
        except Exception as exc:  # noqa: BLE001
            log.warning("could not scan %s: %s", rid, exc)
        if n % 50 == 0:
            save_state(st)
            rate = n / max(time.time() - t0, 1)
            log.info("fetched %s | queue %s | saved %s (match %s, phase %s) | out of scope %s | failed %s | %.2f pages/s", n, len(queue), len(st["done"]),
                     sum(1 for v in st["done"].values() if v["kind"] == "match"), sum(1 for v in st["done"].values() if v["kind"] == "phase"), len(st["out_of_scope"]), len(st["failed"]), rate)
    save_state(st)
    log.info("finished: fetched %s | saved %s | out of scope %s | failed %s | still queued %s", n, len(st["done"]), len(st["out_of_scope"]), len(st["failed"]), len(queue))


if __name__ == "__main__":
    main()
