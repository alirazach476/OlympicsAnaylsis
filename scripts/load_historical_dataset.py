#!/usr/bin/env python3
"""Load athlete_events_through_2026.csv into the warehouse (1960–2026)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.bootstrap import create_schema
from backend.database.session import SessionLocal
from backend.loaders.athlete_events import AthleteEventsLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "data/raw/historical_datasets/athlete_events_through_2026.csv",
    )
    p.add_argument("--min-year", type=int, default=1960)
    p.add_argument("--max-year", type=int, default=2026)
    p.add_argument("--init-schema", action="store_true")
    args = p.parse_args()

    if args.init_schema:
        create_schema()

    session = SessionLocal()
    try:
        summary = AthleteEventsLoader(session, args.csv).load(
            min_year=args.min_year, max_year=args.max_year
        )
        print(summary)
    finally:
        session.close()


if __name__ == "__main__":
    main()
