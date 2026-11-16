#!/usr/bin/env python3
"""Run every analytical module in order and store results in analytics_results / analytics_hypothesis_tests.
Usage: python scripts/run_analytics.py [--only eda,stats,sports,ml]"""
import argparse, os, sys, time
from pathlib import Path
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.analytics import eda, sports, stats
from backend.analytics.store import connect

ap = argparse.ArgumentParser()
ap.add_argument("--only", default="eda,stats,sports,ml")
a = ap.parse_args()
con = connect()
mods = {"eda": eda.run, "stats": stats.run, "sports": sports.run}
for name in a.only.split(","):
    t = time.time()
    if name == "ml":
        from backend.analytics import ml
        r = ml.run(con)
    else:
        r = mods[name](con)
    print(f"{name}: done in {time.time() - t:.0f}s -> {str(r)[:200]}", flush=True)
