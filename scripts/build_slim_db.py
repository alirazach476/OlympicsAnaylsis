"""Build the slim, read-only warehouse used by the free serverless deployment.

The full warehouse (data/olympics_warehouse.db, ~2.7 GB) keeps every crawl artefact. The public API only reads a
subset of it, so this script copies just the tables the API serves into two SQLite shards and:

  * drops raw staging tables that the site only *counts* (their exact row counts are kept in ``_table_counts``),
  * zlib-compresses the large JSON text columns (readers transparently accept either text or compressed bytes),
  * recreates the indexes of every kept table and VACUUMs each shard.

Shards (the serverless host has ~500 MB of /tmp and 2 GB of RAM):
  * ``<out>_disk.db`` - opened read-only from /tmp (main schema),
  * ``<out>_mem0.db``, ``<out>_mem1.db``, ... - each staged in /tmp, copied into a shared in-memory database and
    ATTACHed as ``m0``, ``m1``, ... (kept under ~300 MB so staging never exceeds /tmp).
SQLite resolves unqualified table names across attached databases, so every query runs unchanged.

No value is altered or invented: every kept row is identical after decompression.

Usage:  python scripts/build_slim_db.py [--src data/olympics_warehouse.db] [--out data/olympics_slim] [--compress]

``--compress`` also writes ``<shard>.zst`` (zstandard: ~4x faster to unpack than gzip, which matters for the serverless cold start)
and ``data/manifest.json``; upload those to the Hugging Face dataset under ``slim/``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Tables read by backend/api + backend/viz (found by scanning the code and the OpenAPI routes).
KEEP = [
    "analytics_hypothesis_tests", "analytics_results", "assets", "athlete_id_map", "athlete_participations", "athletes",
    "countries", "crawl_history", "crawl_queue", "data_quality_reports", "disciplines", "event_results", "events", "games",
    "gold_athlete_career", "gold_build_state", "gold_country_medals", "gold_country_participation_history",
    "gold_edition_performance", "gold_event_phases", "gold_event_results", "gold_gender_participation",
    "gold_host_performance", "gold_records", "gold_season_comparison", "gold_sport_performance", "gold_team_sports",
    "historical_nocs", "mascots", "match_results", "match_statistics", "matches", "medal_table_by_event",
    "medal_table_by_sport", "medal_tables", "medals", "olympedia_athlete_results", "olympedia_athlete_xref",
    "olympedia_country_page_tables", "olympedia_country_pages", "olympedia_country_results",
    "olympedia_disqualifications", "olympedia_event_notes", "olympedia_event_rows", "olympedia_match_details",
    "olympedia_match_tables", "olympedia_matches", "olympedia_page_links", "olympedia_page_tables",
    "olympedia_page_text", "olympedia_pages", "olympedia_records_history", "pipeline_runs", "records",
    "silver_athletes", "silver_medal_awards", "silver_participations", "source_pages", "sources", "sport_pictograms",
    "sports", "src_olympics_medallists", "team_members", "teams", "venues", "wikipedia_edition_tables",
    "wikipedia_graph_pages",
]
# Only ever counted by the engineering charts / pipeline-status endpoint -> keep the count, drop the rows.
COUNT_ONLY = ["olympedia_standings", "olympedia_rosters", "src_athlete_bios", "src_athlete_events",
              "src_athlete_results", "wikipedia_links", "wikipedia_pages"]
# Large JSON text columns -> stored as zlib-compressed BLOBs.
COMPRESS = {
    "olympedia_page_tables": {"headers_json", "rows_json", "links_json"},
    "olympedia_match_tables": {"headers_json", "rows_json"},
    "olympedia_country_page_tables": {"headers_json", "rows_json", "links_json"},
    "olympedia_page_text": {"description_json", "section_meta_json"},
    "olympedia_matches": {"participants_json"},
    "match_statistics": {"extra_stats_json"},
}
# The on-disk shard (must stay well under the host's ~500 MB /tmp); everything else goes to the memory shard.
MEM_SHARD_BYTES = 260_000_000
DISK = ["olympedia_page_tables", "event_results", "olympedia_event_rows", "athlete_participations", "silver_participations"]


def _z(v):
    if v is None or isinstance(v, bytes):
        return v
    return zlib.compress(str(v).encode("utf-8"), 9)


def _open(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=OFF")
    c.execute("PRAGMA synchronous=OFF")
    return c


def build(src: Path, out: str) -> list[Path]:
    t0 = time.time()
    paths = {"disk": Path(out + "_disk.db")}
    dst = {"disk": _open(paths["disk"])}

    def mem_target() -> sqlite3.Connection:
        k = f"mem{sum(1 for x in paths if x.startswith('mem')) - 1}"
        if k == "mem-1" or dst[k].execute("PRAGMA page_count").fetchone()[0] * 4096 > MEM_SHARD_BYTES:
            k = f"mem{sum(1 for x in paths if x.startswith('mem'))}"
            paths[k] = Path(out + f"_{k}.db")
            dst[k] = _open(paths[k])
        return dst[k]

    s = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    have = {r[0]: r[1] for r in s.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")}

    dst["disk"].execute("CREATE TABLE _table_counts (name TEXT PRIMARY KEY, n INTEGER NOT NULL)")
    # names of every table in the full warehouse, so the pipeline-status layer counts stay identical
    dst["disk"].execute("CREATE TABLE _warehouse_tables (name TEXT PRIMARY KEY)")
    dst["disk"].executemany("INSERT INTO _warehouse_tables VALUES (?)", [(t,) for t in have])
    for t in COUNT_ONLY:
        if t in have:
            dst["disk"].execute("INSERT INTO _table_counts VALUES (?, ?)", (t, s.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]))

    for t in KEEP:
        if t not in have:
            print(f"  skip {t} (not in source)")
            continue
        d = dst["disk"] if t in DISK else mem_target()
        d.execute(have[t])
        cols = [r[1] for r in s.execute(f'PRAGMA table_info("{t}")')]
        idx = {i for i, c in enumerate(cols) if c in COMPRESS.get(t, set())}
        q = f'INSERT INTO "{t}" VALUES ({",".join("?" * len(cols))})'
        cur, n = s.execute(f'SELECT * FROM "{t}"'), 0
        while batch := cur.fetchmany(5000):
            if idx:
                batch = [tuple(_z(v) if i in idx else v for i, v in enumerate(r)) for r in batch]
            d.executemany(q, batch)
            n += len(batch)
        for (isql,) in s.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (t,)):
            d.execute(isql)
        d.commit()
        print(f"  [{[k for k, v in dst.items() if v is d][0]:5s}] {t:40s} {n:>9,} rows{'  (zlib: ' + ', '.join(sorted(COMPRESS[t])) + ')' if idx else ''}")

    for d in dst.values():
        d.execute("ANALYZE")
        d.commit()
        d.execute("VACUUM")
        d.close()
    s.close()
    for k, p in paths.items():
        print(f"{k:4s} shard {p} : {p.stat().st_size / 1e6:,.1f} MB")
    print(f"built in {time.time() - t0:,.0f}s")
    return list(paths.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data" / "olympics_warehouse.db"))
    ap.add_argument("--out", default=str(ROOT / "data" / "olympics_slim"))
    ap.add_argument("--compress", action="store_true", help="also write <shard>.zst files and manifest.json for upload")
    a = ap.parse_args()
    shards = build(Path(a.src), a.out)
    if a.compress:
        import zstandard

        cctx = zstandard.ZstdCompressor(level=12, threads=-1)
        names = {}
        for p in shards:
            z = Path(str(p) + ".zst")
            with open(p, "rb") as f, open(z, "wb") as g:
                cctx.copy_stream(f, g, size=p.stat().st_size)  # frame records the content size
            names[p.name] = z.name
            print(f"zstd {z} : {z.stat().st_size / 1e6:,.1f} MB")
        disk = next(p for p in shards if p.name.endswith("_disk.db"))
        manifest = {"version": dt.datetime.now().strftime("%Y-%m-%d.%H%M"), "disk": names[disk.name],
                    "mem": [names[p.name] for p in shards if p is not disk]}
        (Path(a.out).parent / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(manifest)


if __name__ == "__main__":
    main()
