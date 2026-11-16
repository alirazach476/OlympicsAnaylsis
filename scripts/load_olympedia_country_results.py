#!/usr/bin/env python3
"""Country route of Olympedia (cached pages are reused, so a rerun is cheap): scrape /countries -> country -> country-edition Results pages, then load olympedia_country_results."""
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.argv = [sys.argv[0], "--delay", "0.3"]
import scrape_olympedia_countries as s  # noqa: E402

s.main()
d = pd.DataFrame(json.loads((ROOT / "data/raw/olympedia/countries/country_results.json").read_text(encoding="utf-8")))
c = sqlite3.connect(ROOT / "data" / "olympics_warehouse.db")
d.to_sql("olympedia_country_results", c, if_exists="replace", index=False)
c.execute("create index if not exists ix_ocr_res on olympedia_country_results(result_id)")
c.execute("create index if not exists ix_ocr_noc on olympedia_country_results(noc,games_id)")
c.commit()
print(f"olympedia_country_results: {len(d):,} rows")
