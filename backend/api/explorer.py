"""Read-only data explorer: paginated, filterable access to the warehouse tables the dashboard pages show (live data only)."""
from __future__ import annotations

import csv
import zlib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from backend.database.session import engine

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
TABLES = {
    "athletes", "athlete_participations", "sports", "disciplines", "events", "event_results", "medals", "medal_tables",
    "medal_table_by_sport", "medal_table_by_event", "teams", "team_members", "matches", "match_statistics", "match_results",
    "venues", "records", "historical_nocs", "countries", "sources", "source_pages", "sport_pictograms", "assets", "mascots",
    "olympedia_event_notes", "olympedia_disqualifications", "data_quality_reports", "games",
}
REPORTS = {
    "completeness": "reports/completeness/completeness_report.csv",
    "missing": "reports/quality/missing_records.csv",
    "duplicates": "reports/quality/duplicate_records.csv",
    "verification": "reports/verification/source_verification_report.csv",
    "failed_pages": "reports/scraping/failed_pages.csv",
}


def _present_cols(table: str) -> list[str]:
    # PRAGMA without a schema searches main and attached databases (the slim deployment keeps a shard in memory).
    with engine.connect() as con:
        return [r[1] for r in con.execute(text(f'PRAGMA table_info("{table}")')).all()]


def _cols(table: str) -> list[str]:
    if table not in TABLES:
        raise HTTPException(404, f"unknown table {table}")
    cols = _present_cols(table)
    if not cols:
        raise HTTPException(404, f"table {table} not present")
    return cols


def _cell(v):
    if isinstance(v, (bytes, memoryview)):  # zlib-compressed JSON in the slim deployment DB
        try:
            return zlib.decompress(bytes(v)).decode("utf-8")
        except zlib.error:
            return None
    return v


@router.get("/explorer/tables")
def tables() -> list[dict]:
    out = []
    with engine.connect() as con:
        for t in sorted(TABLES):
            if _present_cols(t):
                out.append({"table": t, "rows": con.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()})
    return out


@router.get("/explorer/{table}")
def rows(table: str, games_id: Optional[str] = None, noc: Optional[str] = None, season: Optional[str] = None,
         q: Optional[str] = Query(None, description="substring match on text columns"), page: int = 1,
         page_size: int = Query(50, le=500)) -> dict:
    cols = _cols(table)
    where, params = [], {}
    if games_id and "games_id" in cols:
        where.append("games_id = :g")
        params["g"] = games_id
    if season and "games_id" in cols:
        where.append("games_id LIKE :s")
        params["s"] = f"%_{season.lower()}"
    if season and "season" in cols:
        where.append("LOWER(season) = :se")
        params["se"] = season.lower()
    for key in ("noc_code", "noc"):
        if noc and key in cols:
            where.append(f"{key} = :n")
            params["n"] = noc.upper()
            break
    if q:
        textcols = [c for c in cols if any(k in c for k in ("name", "event", "sport", "title", "note", "description", "team", "city", "url"))][:6]
        if textcols:
            where.append("(" + " OR ".join(f'LOWER(CAST("{c}" AS TEXT)) LIKE :q' for c in textcols) + ")")
            params["q"] = f"%{q.lower()}%"
    w = (" WHERE " + " AND ".join(where)) if where else ""
    with engine.connect() as con:
        total = con.execute(text(f'SELECT COUNT(*) FROM "{table}"{w}'), params).scalar()
        data = con.execute(text(f'SELECT * FROM "{table}"{w} LIMIT :lim OFFSET :off'),
                           {**params, "lim": page_size, "off": (max(page, 1) - 1) * page_size}).mappings().all()
    return {"table": table, "columns": cols, "total": total, "page": page, "page_size": page_size, "rows": [{k: _cell(v) for k, v in r.items()} for r in data]}


@router.get("/reports/{name}")
def report(name: str) -> dict:
    p = REPORTS.get(name)
    if not p or not (ROOT / p).exists():
        raise HTTPException(404, f"report {name} not generated yet")
    with (ROOT / p).open(encoding="utf-8") as f:
        r = list(csv.DictReader(f))
    return {"name": name, "columns": list(r[0].keys()) if r else [], "total": len(r), "rows": r}
