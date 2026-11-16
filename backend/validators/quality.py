"""Data quality / completeness reporting (Phase 1 scaffold + crawl metrics)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.core import Athlete, Event, EventResult, Game, MedalTable, Sport
from backend.models.enums import CrawlStatus
from backend.models.wikipedia import CrawlQueue, WikipediaLink, WikipediaPage


def edition_completeness(session: Session, games_id: str) -> dict:
    def count(model, *filters):
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        return int(session.scalar(stmt) or 0)

    return {
        "games_id": games_id,
        "athletes": count(Athlete),  # global until participation filter exists densely
        "sports": count(Sport),
        "events": count(Event, Event.games_id == games_id),
        "results": count(EventResult, EventResult.games_id == games_id),
        "medal_table_rows": count(MedalTable, MedalTable.games_id == games_id),
        "wikipedia_crawled": count(
            WikipediaPage,
            WikipediaPage.games_id == games_id,
            WikipediaPage.crawl_status == CrawlStatus.CRAWLED.value,
        ),
        "wikipedia_pending": count(
            CrawlQueue,
            CrawlQueue.games_id == games_id,
            CrawlQueue.status == CrawlStatus.PENDING.value,
        ),
        "wikipedia_failed": count(
            CrawlQueue,
            CrawlQueue.games_id == games_id,
            CrawlQueue.status == CrawlStatus.FAILED.value,
        ),
        "wikipedia_links": count(WikipediaLink, WikipediaLink.games_id == games_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "complete": False,
        "notes": "Completion requires multi-source verification — crawl finish ≠ complete.",
    }


def write_reports(session: Session, games_id: Optional[str] = None) -> dict:
    settings = get_settings()
    completeness_dir = settings.reports_dir / "completeness"
    scraping_dir = settings.reports_dir / "scraping"
    completeness_dir.mkdir(parents=True, exist_ok=True)
    scraping_dir.mkdir(parents=True, exist_ok=True)

    games_ids = [games_id] if games_id else [
        g for (g,) in session.execute(select(Game.games_id)).all()
    ]
    rows = [edition_completeness(session, gid) for gid in games_ids]

    csv_path = completeness_dir / "completeness_report.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    failed = session.execute(
        select(
            CrawlQueue.games_id,
            CrawlQueue.url,
            CrawlQueue.last_error,
            CrawlQueue.attempts,
        ).where(CrawlQueue.status == CrawlStatus.FAILED.value)
    ).all()
    failed_path = scraping_dir / "failed_pages.csv"
    with failed_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["games_id", "url", "last_error", "attempts"])
        for row in failed:
            writer.writerow(row)

    summary = {
        "editions": len(rows),
        "completeness_report": str(csv_path),
        "failed_pages": str(failed_path),
        "rows": rows,
    }
    summary_path = scraping_dir / "crawl_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
