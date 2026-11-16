#!/usr/bin/env python3
"""Re-parse cached Olympedia match HTML into JSON with the current parser."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scrapers.olympedia.results import OlympediaResultsScraper

scraper = OlympediaResultsScraper(session=None, delay=0)
root = Path("data/raw/olympedia/editions")
fixed = 0
total = 0
for html_path in root.glob("*/matches/*.html"):
    total += 1
    games_id = html_path.parts[-3]
    rid = html_path.stem
    # seed metadata from existing json if present
    jpath = html_path.with_suffix(".json")
    meta = {}
    if jpath.exists():
        try:
            meta = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    html = html_path.read_text(encoding="utf-8", errors="replace")
    fx = scraper.parse_match_page(
        games_id=meta.get("games_id") or games_id,
        sport_name=meta.get("sport_name") or "Unknown",
        event_name=meta.get("event_name") or "",
        match_label=meta.get("match_label") or rid,
        result_id=str(meta.get("result_id") or rid),
        url=meta.get("url") or f"https://www.olympedia.org/results/{rid}",
        html=html,
    )
    from dataclasses import asdict

    jpath.write_text(json.dumps(asdict(fx), ensure_ascii=False, indent=2), encoding="utf-8")
    if fx.home_noc or fx.away_noc:
        fixed += 1
print(json.dumps({"html_files": total, "with_noc": fixed}))
