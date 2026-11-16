#!/usr/bin/env python3
"""Materialise the whole Dagster asset graph in-process (no webserver). Use `dagster dev -m backend.pipeline.dagster_defs` for the UI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dagster import materialize
from backend.pipeline.dagster_defs import analytics_results, bronze_inventory, noc_registry, podium_results, silver_and_gold_marts, validation_report

res = materialize([bronze_inventory, podium_results, noc_registry, silver_and_gold_marts, analytics_results, validation_report], raise_on_error=True)
print("success:", res.success)
for ev in res.get_asset_materialization_events():
    print(" -", ev.asset_key.to_user_string(), {k: str(v.value)[:80] for k, v in ev.materialization.metadata.items()})
