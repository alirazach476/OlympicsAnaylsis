#!/usr/bin/env python3
"""Run backend/validators/expectations.py against the warehouse; write reports/quality/validation_results.csv and one data_quality_reports row."""
import csv, datetime as dt, json, sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.validators.expectations import run_all

c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=120)
res = run_all(c)
out = ROOT / "reports/quality/validation_results.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["check", "passed", "observed", "detail"])
    w.writeheader()
    w.writerows(res)
now = dt.datetime.now(dt.timezone.utc).isoformat()
c.execute("INSERT INTO data_quality_reports(games_id,report_type,metrics_json,report_path,generated_at,created_at,updated_at) VALUES (NULL,'validation',?,?,?,?,?)",
          (json.dumps(res), str(out.relative_to(ROOT)), now, now, now))
c.commit()
for r in res:
    print(("PASS " if r["passed"] else "FAIL ") + r["check"], r["observed"], "-", r["detail"])
print(f"{sum(r['passed'] for r in res)}/{len(res)} passed")
