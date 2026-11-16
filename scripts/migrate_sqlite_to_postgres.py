#!/usr/bin/env python3
"""Copy the SQLite warehouse into PostgreSQL (psycopg2). NOT run here: no Postgres server is available in this environment.

    docker compose up -d postgres
    python scripts/migrate_sqlite_to_postgres.py --pg "postgresql://olympics:change_me@localhost:5432/olympics"

Creates every table (types mapped from SQLite affinity), copies rows in batches, never modifies the SQLite file, and is re-runnable
(--replace drops and recreates tables; without it existing tables are skipped).
"""
import argparse, sqlite3
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--pg", required=True)
ap.add_argument("--replace", action="store_true")
ap.add_argument("--batch", type=int, default=20000)
a = ap.parse_args()
src = sqlite3.connect(f"file:{ROOT / 'data/olympics_warehouse.db'}?mode=ro", uri=True)
pg = psycopg2.connect(a.pg)
cur = pg.cursor()


def pgtype(t: str) -> str:
    t = (t or "").upper()
    if "INT" in t: return "BIGINT"
    if any(k in t for k in ("REAL", "FLOA", "DOUB")): return "DOUBLE PRECISION"
    if "BOOL" in t: return "BOOLEAN"
    return "TEXT"


for (name,) in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
    cols = src.execute(f'PRAGMA table_info("{name}")').fetchall()
    cur.execute("SELECT to_regclass(%s)", (name,))
    exists = cur.fetchone()[0] is not None
    if exists and not a.replace:
        print("skip", name); continue
    if exists: cur.execute(f'DROP TABLE "{name}" CASCADE')
    pk = [c[1] for c in cols if c[5]]
    defs = [f'"{c[1]}" {pgtype(c[2])}' + (" NOT NULL" if c[3] and not c[5] else "") for c in cols]
    if pk: defs.append("PRIMARY KEY (" + ",".join(f'"{k}"' for k in pk) + ")")
    cur.execute(f'CREATE TABLE "{name}" (' + ",".join(defs) + ")")
    n = 0
    q = src.execute(f'SELECT * FROM "{name}"')
    while True:
        rows = q.fetchmany(a.batch)
        if not rows: break
        execute_values(cur, f'INSERT INTO "{name}" VALUES %s', rows); n += len(rows)
    pg.commit(); print(f"{name}: {n} rows", flush=True)
pg.close()
