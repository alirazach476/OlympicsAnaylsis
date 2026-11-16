#!/usr/bin/env python3
"""Print / export the Olympic editions master registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.collectors.editions import all_editions, editions_by_season


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--season", choices=["summer", "winter"])
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    editions = editions_by_season(args.season) if args.season else all_editions()
    payload = [e.to_dict() for e in editions]
    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {len(payload)} editions -> {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
