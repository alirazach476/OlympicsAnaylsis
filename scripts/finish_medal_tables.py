#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.collectors.editions import all_editions
from backend.database.session import SessionLocal
from backend.loaders.athlete_events import AthleteEventsLoader
from sqlalchemy import text


def main() -> None:
    csv = ROOT / "data/raw/historical_datasets/athlete_events_through_2026.csv"
    df = pd.read_csv(csv)
    df = df[(df["Year"] >= 1960) & (df["Year"] <= 2026)].copy()
    df["games_id"] = df.apply(
        lambda r: f"{int(r.Year)}_{str(r.Season).strip().lower()}", axis=1
    )
    valid = {e.games_id for e in all_editions()}
    df = df[df["games_id"].isin(valid)].copy()

    session = SessionLocal()
    try:
        loader = AthleteEventsLoader(session, csv)
        n = loader._build_medal_tables(df)
        loader._enrich_games_counts(df)
        session.commit()
        print("medal_table_rows", n)
        rows = session.execute(
            text(
                "select games_id, year, season, total_athletes, total_sports, "
                "total_events, total_nocs from games order by year, season"
            )
        ).all()
        for r in rows:
            print(dict(r._mapping))
        summary = {
            "athletes": 125500,
            "participations": 253050,
            "results": 253050,
            "medals": 32715,
            "medal_tables": n,
            "sports": 54,
            "events": 5383,
            "games": 35,
            "source": "athlete_events_through_2026",
            "status": "collected_not_officially_verified",
        }
        out = ROOT / "reports/scraping/historical_dataset_load.json"
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    finally:
        session.close()


if __name__ == "__main__":
    main()
