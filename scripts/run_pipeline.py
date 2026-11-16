#!/usr/bin/env python3
"""One-command, restartable ETL over data already collected (stand-in for Dagster, which is not installed here).

Stages run in order and every stage is idempotent, so re-running after an interruption is safe. Network scrapers are NOT part of this
runner (they are resumable on their own); this runs the offline LOAD / TRANSFORM / VALIDATE / EXPORT stages.
Usage: python scripts/run_pipeline.py [--from STAGE] [--only STAGE,STAGE]
"""
import argparse, datetime as dt, json, sqlite3, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
STAGES = [
    ("load_csv_folder", "load_athlete_events_folder.py"),
    ("link_athletes", "link_athletes_to_bios.py"),
    ("link_athletes_olympedia", "link_athletes_to_olympedia_results.py"),
    ("add_missing_athletes", "add_missing_olympedia_athletes.py"),
    ("merge_bios_duplicates", "merge_bios_duplicate_athletes.py"),
    ("olympedia_countries", "load_olympedia_country_results.py"),
    ("olympedia_edition_pages", "load_olympedia_edition_pages.py"),
    ("olympedia_page_tables", "load_olympedia_page_tables.py"),
    ("olympedia_page_text", "load_olympedia_page_text.py"),
    ("olympedia_country_pages", "load_olympedia_country_page_tables.py"),
    ("round_results", "build_round_results.py"),
    ("page_links", "build_page_links.py"),
    ("athlete_stat_gaps", "fill_athlete_stat_gaps.py"),
    ("event_result_values", "fill_event_result_values.py"),
    ("event_marks_from_rounds", "fill_event_marks_from_rounds.py"),
    ("fix_football_matches", "fix_football_matches.py"),
    ("match_statistics", "load_match_statistics.py"),
    ("team_members", "load_team_members.py"),
    ("records", "load_olympedia_records.py"),
    ("venues", "load_olympedia_venues.py"),
    ("wiki_graph", "load_wikipedia_edition_graph.py"),
    ("wiki_reference", "load_wikipedia_reference_pages.py"),
    ("assets", "sync_assets.py"),
    ("flags", "download_flags.py"),
    ("asset_registry", "build_edition_asset_registry.py"),
    ("derive_master_fields", "derive_master_fields.py"),
    ("iso_disciplines", "derive_iso_and_disciplines.py"),
    ("continents_shared", "derive_continents_and_shared_medals.py"),
    ("team_flags", "derive_team_flags_and_reallocations.py"),
    ("disqualifications", "derive_disqualifications.py"),
    ("podium_results", "extract_podium_results.py"),
    ("noc_registry", "fix_noc_registry.py"),
    ("medallion", "build_medallion.py"),
    ("analytics", "run_analytics.py"),
    ("optimize", "optimize_db.py"),
    ("inventory_audit", "audit_inventory.py"),
    ("quality_reports", "build_quality_reports.py"),
    ("validation", "run_validation.py"),
    ("viz_coverage", "build_viz_coverage.py"),
    ("analysis_report", "build_analysis_report.py"),
    ("export", "export_warehouse.py"),
    ("parquet", "export_gold_parquet.py"),
]
ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="start")
ap.add_argument("--only")
a = ap.parse_args()
names = [n for n, _ in STAGES]
run = STAGES
if a.start:
    run = STAGES[names.index(a.start):]
if a.only:
    want = a.only.split(",")
    run = [s for s in STAGES if s[0] in want]
def log_run(stage, started, finished, status, script):
    """Record each stage in pipeline_runs (used by the pipeline-timeline chart); logging must never break the pipeline."""
    try:
        c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=60)
        c.execute("PRAGMA busy_timeout=60000")
        c.execute("INSERT INTO pipeline_runs(stage, started_at, finished_at, status, detail) VALUES (?,?,?,?,?)",
                  (stage, started, finished, status, json.dumps({"script": script, "runner": "run_pipeline.py"})))
        c.commit(); c.close()
    except Exception as exc:  # noqa: BLE001
        print(f"(pipeline_runs not updated: {exc})", flush=True)


for name, script in run:
    t = time.time()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    print(f"=== {name} ({script})", flush=True)
    r = subprocess.run([sys.executable, "-X", "utf8", str(S / script)], cwd=ROOT)
    print(f"=== {name}: {'ok' if r.returncode == 0 else 'FAILED'} in {time.time() - t:.0f}s", flush=True)
    log_run(name, started, dt.datetime.now(dt.timezone.utc).isoformat(), "success" if r.returncode == 0 else "failed", script)
    if r.returncode and name != "validation":  # validation failures are findings, other failures stop the run
        sys.exit(r.returncode)
