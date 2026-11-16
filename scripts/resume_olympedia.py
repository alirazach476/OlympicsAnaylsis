#!/usr/bin/env python3
"""Resume Olympedia scrape from disk cache after reboot/crash.

Skips events that already have JSON under data/raw/olympedia/editions/*/events/.
Writes data/raw/olympedia/checkpoint.json after every event.
GPU cannot accelerate HTTP scraping — not used.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run(args: list[str]) -> int:
    logging.info("RUN %s", " ".join(args))
    return subprocess.call([sys.executable, *args], cwd=str(ROOT))


def main() -> None:
    # sync fixtures first
    run(["scripts/load_olympedia_fixtures.py"])
    # single stream: winter then summer (resume skips cached)
    rc1 = run(
        [
            "scripts/scrape_olympedia_results.py",
            "--winter-only",
            "--no-db",
            "--delay",
            "1.2",
        ]
    )
    run(["scripts/load_olympedia_fixtures.py"])
    rc2 = run(
        [
            "scripts/scrape_olympedia_results.py",
            "--summer-only",
            "--no-db",
            "--delay",
            "1.2",
        ]
    )
    run(["scripts/load_olympedia_fixtures.py"])
    run(["scripts/load_olympedia_sports_catalog.py"])
    cp = ROOT / "data" / "raw" / "olympedia" / "checkpoint.json"
    logging.info("checkpoint file: %s exists=%s", cp, cp.exists())
    raise SystemExit(0 if rc1 == 0 and rc2 == 0 else 1)


if __name__ == "__main__":
    main()
