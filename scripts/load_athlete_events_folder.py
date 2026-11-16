#!/usr/bin/env python3
"""Load the CSVs in athlete_events.csv/ into the warehouse as raw src_* tables (re-runnable).

bios.csv / results.csv carry mojibake (UTF-8 read as cp1252); it is repaired on load.
"""
import sqlite3, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "athlete_events.csv"
DB = ROOT / "data" / "olympics_warehouse.db"

def fix(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except Exception:
        return s

def main():
    con = sqlite3.connect(DB, timeout=120)
    con.execute("PRAGMA busy_timeout=120000")
    jobs = {
        "src_athlete_events": ("athlete_events.csv", {}),
        "src_noc_regions": ("noc_regions.csv", {}),
        "src_athlete_bios": ("bios.csv", {}),
        "src_athlete_results": ("results.csv", {}),
        "src_olympics_medallists": ("olympics.csv", {"skiprows": None}),
    }
    for table, (fn, _) in jobs.items():
        p = SRC / fn
        if table == "src_olympics_medallists":
            raw = pd.read_csv(p, header=None, dtype=str, keep_default_na=False, encoding="utf-8", encoding_errors="replace", on_bad_lines="skip")
            h = raw.index[raw[0] == "City"][0]
            df = raw.iloc[h + 1:].copy(); df.columns = list(raw.iloc[h])
        else:
            df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8", encoding_errors="replace")
        if table in ("src_athlete_bios", "src_athlete_results"):
            for col in df.columns:
                df[col] = df[col].map(fix)
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        df.to_sql(table, con, if_exists="replace", index=False, chunksize=20000)
        print(table, len(df), flush=True)
    for t, col in (("src_athlete_events", "ID"), ("src_athlete_bios", "athlete_id"), ("src_athlete_results", "athlete_id")):
        con.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_id ON {t}({col})")
    con.commit()

if __name__ == "__main__":
    main()
