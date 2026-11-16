"""Dagster definitions for the Olympics platform (Bronze -> Silver -> Gold -> Analytics -> Validation).

Each asset runs one idempotent script and reports row counts as metadata. Re-materialising an asset never deletes earlier successful
results of *other* assets, and the Gold build is incremental per Games (see scripts/build_medallion.py).

Run the UI:      dagster dev -m backend.pipeline.dagster_defs
Run headless:    python scripts/run_dagster.py
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

from dagster import AssetExecutionContext, Definitions, MaterializeResult, MetadataValue, asset, define_asset_job

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "olympics_warehouse.db"


def _run(script: str, *args: str) -> str:
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / script), *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{script} failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


def _count(tables: list[str]) -> dict:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


@asset(group_name="extract", description="Bronze audit: inventory of every table/file/raw store (read-only).")
def bronze_inventory(context: AssetExecutionContext) -> MaterializeResult:
    out = _run("audit_inventory.py")
    context.log.info(out[-600:])
    return MaterializeResult(metadata={"tables": _count(["games", "athletes", "events", "medals"]), "report": MetadataValue.path(str(ROOT / "reports/data_inventory/inventory.md"))})


@asset(group_name="extract", deps=[bronze_inventory], description="Podium result strings re-parsed from cached Olympedia event pages (Bronze -> bronze-derived table).")
def podium_results(context: AssetExecutionContext) -> MaterializeResult:
    context.log.info(_run("extract_podium_results.py")[-400:])
    return MaterializeResult(metadata=_count(["olympedia_podium_results"]))


@asset(group_name="clean", deps=[podium_results], description="NOC registry repair + reference aliases (idempotent).")
def noc_registry(context: AssetExecutionContext) -> MaterializeResult:
    context.log.info(_run("fix_noc_registry.py")[-300:])
    return MaterializeResult(metadata=_count(["historical_nocs", "ref_noc_alias"]))


@asset(group_name="clean", deps=[noc_registry], description="Silver + Gold marts (incremental per Games).")
def silver_and_gold_marts(context: AssetExecutionContext) -> MaterializeResult:
    out = _run("build_medallion.py")
    context.log.info(out[-800:])
    return MaterializeResult(metadata=_count(["silver_participations", "silver_country_medals", "gold_edition_performance", "gold_country_medals", "gold_athlete_career"]))


@asset(group_name="transform", deps=[silver_and_gold_marts], description="Statistics, regressions, time series and ML results (analytics_* tables).")
def analytics_results(context: AssetExecutionContext) -> MaterializeResult:
    out = _run("run_analytics.py")
    context.log.info(out[-800:])
    return MaterializeResult(metadata=_count(["analytics_hypothesis_tests"]))


@asset(group_name="validate", deps=[analytics_results], description="Expectation-style validation + Gold reconciliation tests.")
def validation_report(context: AssetExecutionContext) -> MaterializeResult:
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "run_validation.py")], cwd=ROOT, capture_output=True, text=True)
    context.log.info(r.stdout[-1200:])  # failing checks are findings, not pipeline crashes
    return MaterializeResult(metadata={"summary": r.stdout.strip().splitlines()[-1] if r.stdout else "no output"})


full_pipeline = define_asset_job("full_pipeline", selection="*")
defs = Definitions(assets=[bronze_inventory, podium_results, noc_registry, silver_and_gold_marts, analytics_results, validation_report], jobs=[full_pipeline])
