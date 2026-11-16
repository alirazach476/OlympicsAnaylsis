#!/usr/bin/env python3
"""Audit of the Olympedia scrape against the collection rule: every results page of every edition, every dropdown option on it (phases, runs,
standings, parts, heats ...), and every match / bout link inside - each fetched and saved.

For every cached event page (events/*.html) and phase page (phases/*.html) it reads
  * all <select> dropdowns except the two navigation menus (same_games_select / other_games_select) and lists every option that points at /results/<id>
  * all <a href="/results/<id>"> links in the page body (not the navigation bar, the breadcrumb, the record row or the footer)
and checks that each target exists locally (events, phases or matches folder of any edition). Writes reports/scraping/olympedia_audit.json + .md and
data/raw/olympedia/missing_pages.json (the worklist for scripts/scrape_olympedia_missing.py).   Usage: python scripts/audit_olympedia_scrape.py"""
import json
import re
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "olympedia" / "editions"
OUT = ROOT / "reports" / "scraping"
NAV_SELECTS = {"same_games_select", "other_games_select"}


def local_ids() -> dict[str, tuple[str, str]]:
    ids = {}
    for g in RAW.iterdir():
        if not g.is_dir():
            continue
        for kind in ("events", "phases", "matches"):
            d = g / kind
            if d.exists():
                for f in d.glob("*.html"):
                    ids[f.stem] = (g.name, kind)
    return ids


def scan(path_s: str):
    path = Path(path_s)
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    own = path.stem
    games = path.parts[-3]
    h1 = soup.select_one("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    opts, links, selects = [], [], []
    for sel in soup.select("select"):
        sid = sel.get("id") or sel.get("name") or "?"
        if sid in NAV_SELECTS:
            continue
        o = [(opt.get("value") or "").strip() for opt in sel.select("option")]
        o = [v for v in o if v.isdigit()]
        selects.append((sid, len(o)))
        for opt in sel.select("option"):
            v = (opt.get("value") or "").strip()
            if v.isdigit() and v != own:
                opts.append((sid, v, opt.get_text(" ", strip=True)[:60]))
    for nav in soup.select("nav, .navbar, .breadcrumb, footer, tr.records, select"):
        nav.decompose()
    for a in soup.select("a[href*='/results/']"):
        m = re.search(r"/results/(\d+)", a.get("href") or "")
        if m and m.group(1) != own:
            links.append((m.group(1), a.get_text(" ", strip=True)[:60]))
    return {"file": path_s, "games": games, "own": own, "kind": path.parts[-2], "title": title, "selects": selects, "options": opts, "links": links}


def main():
    have = local_ids()
    files = [str(p) for g in RAW.iterdir() if g.is_dir() for k in ("events", "phases") for p in sorted((g / k).glob("*.html"))]
    print(f"{len(have):,} local pages; scanning {len(files):,} event/phase pages ...", flush=True)
    with Pool(4) as pool:
        res = pool.map(scan, files, chunksize=100)
    sel_ids = Counter()
    sel_opts = Counter()
    missing_opts, missing_links = {}, {}
    for r in res:
        for sid, n in r["selects"]:
            key = re.sub(r"\d+", "N", sid)
            sel_ids[key] += 1
            sel_opts[key] += n
        for sid, v, label in r["options"]:
            if v not in have:
                missing_opts.setdefault(v, {"id": v, "games": r["games"], "select": re.sub(r"\d+", "N", sid), "label": label, "found_on": r["own"], "kind": "dropdown option"})
        for v, label in r["links"]:
            if v not in have:
                missing_links.setdefault(v, {"id": v, "games": r["games"], "select": "", "label": label, "found_on": r["own"], "kind": "page link"})
    missing = {**missing_links, **missing_opts}
    # a target that exists as an edition event under another games_id is fine; ids outside our 35 editions are out of scope
    ev_by = Counter(r["kind"] for r in res)
    # catalog check: every event of the edition catalogs is present
    cat_missing = []
    for g in sorted(RAW.iterdir()):
        cp = g / "events_catalog.json"
        if not cp.exists():
            continue
        for row in json.loads(cp.read_text(encoding="utf-8")):
            rid = str(row.get("result_id") or row.get("id") or "")
            if rid and not (g / "events" / f"{rid}.html").exists():
                cat_missing.append({"id": rid, "games": g.name, "label": row.get("event_name") or row.get("name")})
    summary = {"local_pages": len(have), "event_pages": ev_by.get("events", 0), "phase_pages": ev_by.get("phases", 0), "match_pages": sum(1 for v in have.values() if v[1] == "matches"),
               "dropdown_ids": dict(sel_ids), "dropdown_options_by_id": dict(sel_opts), "missing_total": len(missing), "missing_by_kind": dict(Counter(m["kind"] for m in missing.values())),
               "missing_by_games": dict(Counter(m["games"] for m in missing.values())), "catalog_events_missing": len(cat_missing)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "olympedia_audit.json").write_text(json.dumps({"summary": summary, "missing": list(missing.values()), "catalog_missing": cat_missing}, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "data" / "raw" / "olympedia" / "missing_pages.json").write_text(json.dumps(list(missing.values()), indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["# Olympedia scrape audit\n", f"Event pages {summary['event_pages']:,}, phase (dropdown) pages {summary['phase_pages']:,}, match / bout pages {summary['match_pages']:,}.\n",
          "## Dropdowns found on result pages (navigation menus excluded)\n", "| select id (digits -> N) | pages | options |\n|---|---|---|"]
    for k, v in sel_ids.most_common():
        md.append(f"| `{k}` | {v:,} | {sel_opts[k]:,} |")
    md.append(f"\n## Not yet scraped: {summary['missing_total']:,} pages\n")
    md.append(f"By kind: {summary['missing_by_kind']}.  Events in catalogs without a saved page: {len(cat_missing)}.\n")
    for m in list(missing.values())[:40]:
        md.append(f"- {m['games']} / {m['id']} ({m['kind']}, {m['select'] or 'link'}): {m['label']} - found on {m['found_on']}")
    (OUT / "olympedia_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
