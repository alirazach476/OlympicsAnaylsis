"""Report sports/events present vs deep-scraped standings/fixtures."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from backend.collectors.editions import all_editions

root = Path("data/raw/olympedia/editions")
report = []
for ed in all_editions():
    g = ed.games_id
    cat_path = root / g / "events_catalog.json"
    if not cat_path.exists():
        report.append({"games_id": g, "status": "NO_CATALOG"})
        continue
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    by_sport = defaultdict(list)
    for row in catalog:
        by_sport[row["sport_name"]].append(row)

    events_dir = root / g / "events"
    scraped_ids = set()
    if events_dir.exists():
        scraped_ids = {p.stem for p in events_dir.glob("*.json")}

    sports = []
    missing_event_pages = 0
    for sport, evs in sorted(by_sport.items()):
        scraped = sum(1 for e in evs if e["result_id"] in scraped_ids)
        missing = len(evs) - scraped
        missing_event_pages += missing
        sports.append(
            {
                "sport": sport,
                "events": len(evs),
                "event_pages_scraped": scraped,
                "event_pages_missing": missing,
                "complete": missing == 0,
            }
        )
    report.append(
        {
            "games_id": g,
            "season": ed.season,
            "sports_count": len(by_sport),
            "events_count": len(catalog),
            "event_pages_scraped": len(scraped_ids),
            "event_pages_missing": missing_event_pages,
            "sports_complete": sum(1 for s in sports if s["complete"]),
            "sports_incomplete": sum(1 for s in sports if not s["complete"]),
            "sports": sports,
        }
    )

out = {
    "summary": {
        "editions": len(report),
        "editions_with_catalog": sum(1 for r in report if r.get("events_count")),
        "total_events": sum(r.get("events_count", 0) for r in report),
        "total_event_pages_scraped": sum(r.get("event_pages_scraped", 0) for r in report),
        "total_event_pages_missing": sum(r.get("event_pages_missing", 0) for r in report),
    },
    "editions": report,
}
Path("data/exports/sports_detail_gaps.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out["summary"], indent=2))
print("---")
for r in report:
    if not r.get("events_count"):
        print(f"{r['games_id']}: NO CATALOG")
        continue
    print(
        f"{r['games_id']:14} sports={r['sports_count']:3} events={r['events_count']:4} "
        f"scraped_pages={r['event_pages_scraped']:4} MISSING_pages={r['event_pages_missing']:4} "
        f"sports_done={r['sports_complete']}/{r['sports_count']}"
    )
