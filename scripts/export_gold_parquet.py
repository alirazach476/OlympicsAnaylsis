#!/usr/bin/env python3
"""Columnar (Parquet) copies of the Gold + Silver layers using Polars - fast to load for notebooks / BI tools. Writes data/exports/parquet/*.parquet."""
import sqlite3
from pathlib import Path
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "exports" / "parquet"
OUT.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(f"file:{ROOT / 'data/olympics_warehouse.db'}?mode=ro", uri=True)
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if (r[0].startswith("gold_") or r[0].startswith("silver_")) and r[0] != "gold_build_state"]
for t in tables:
    df = pl.read_database(f'SELECT * FROM "{t}"', con, infer_schema_length=None)
    df.write_parquet(OUT / f"{t}.parquet", compression="zstd")
    print(f"{t}.parquet  {df.height:,} rows x {df.width} cols  {(OUT / f'{t}.parquet').stat().st_size / 1e6:.1f} MB")
