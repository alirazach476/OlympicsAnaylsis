"""Visualization API: /api/viz/* - chart payloads, registry, filter options, drill-down and coverage (see backend/viz)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.viz import REGISTRY, SECTIONS, Unavailable, evaluate
from backend.viz.core import df, noc_names

router = APIRouter(prefix="/viz", tags=["visualizations"])
COVERAGE = Path(__file__).resolve().parents[2] / "reports" / "visualization" / "coverage.json"


def _coverage_status() -> dict[str, dict]:
    if COVERAGE.exists():
        try:
            return {c["id"]: c for c in json.loads(COVERAGE.read_text(encoding="utf-8")).get("charts", [])}
        except Exception:  # noqa: BLE001
            return {}
    return {}


@router.get("/registry")
def registry(section: Optional[int] = None, page: Optional[str] = None):
    st = _coverage_status()
    out = []
    for s in REGISTRY.values():
        if (section and s.section != section) or (page and s.page != page):
            continue
        m = s.meta()
        m["status"] = st.get(s.id, {}).get("status", "implemented")
        m["status_reason"] = st.get(s.id, {}).get("reason", "")
        out.append(m)
    return {"sections": {str(k): v for k, v in SECTIONS.items()}, "charts": out, "total": len(out)}


@router.get("/options")
def options():
    games = df("SELECT games_id, year, season, host_city FROM games WHERE games_id IN (SELECT games_id FROM gold_edition_performance) ORDER BY year, season")
    names = noc_names()
    nocs = df("SELECT DISTINCT noc_code FROM gold_country_medals ORDER BY noc_code").noc_code.tolist()
    sports = df("SELECT sport_name, SUM(athletes) a FROM gold_sport_performance GROUP BY 1 ORDER BY 2 DESC").sport_name.tolist()
    rec = df("SELECT description FROM gold_records")
    rec["event"] = rec.description.str.split(" | ", regex=False).str[0]
    rc = rec.event.value_counts()
    team = df("SELECT sport_name, COUNT(*) n FROM olympedia_matches WHERE home_score GLOB '[0-9]*' GROUP BY 1 HAVING n>=100 ORDER BY n DESC")
    ev = df("SELECT DISTINCT games_id, sport_name, event_name FROM olympedia_matches WHERE stage LIKE '%Match 1/2%' AND home_score GLOB '[0-9]*' ORDER BY games_id")
    return {"games": games.to_dict("records"), "nocs": [{"code": c, "name": names.get(c, {}).get("name", c)} for c in nocs], "sports": sports,
            "record_events": rc[rc >= 3].index.tolist(), "team_sports": team.sport_name.tolist(), "team_events": ev.to_dict("records"),
            "ml_models": ["logistic_regression", "random_forest", "xgboost"], "correlation_methods": ["pearson", "spearman", "kendall"],
            "stat_variables": ["athlete_age", "country_edition_total_medals", "country_edition_athletes"]}


@router.get("/search/athletes")
def search_athletes(q: str = Query("", min_length=0), limit: int = Query(15, le=50)):
    if len(q.strip()) < 2:
        d = df("SELECT athlete_id, full_name, gender, medals, games_count FROM gold_athlete_career ORDER BY medals DESC, gold DESC LIMIT :n", n=limit)
    else:
        d = df("SELECT athlete_id, full_name, gender, medals, games_count FROM gold_athlete_career WHERE full_name LIKE :q ORDER BY medals DESC, games_count DESC LIMIT :n", q=f"%{q.strip()}%", n=limit)
    return json.loads(d.to_json(orient="records"))


@router.get("/chart/{chart_id}")
def chart(chart_id: str, request: Request, format: Optional[str] = None):
    spec = REGISTRY.get(chart_id)
    if not spec:
        raise HTTPException(404, f"unknown chart {chart_id}")
    params = dict(request.query_params)
    params.pop("format", None)
    try:
        p = evaluate(spec, params)
    except Unavailable as exc:
        if format == "csv":
            raise HTTPException(404, str(exc))
        return {"id": spec.id, "title": spec.name, "status": "unavailable", "reason": str(exc), "kind": spec.kind, "alternatives": list(spec.alternatives)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"{type(exc).__name__}: {exc}")
    p["status"] = "ok"
    if format == "csv":
        t = p["table"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(t["columns"])
        for r in t["rows"]:
            w.writerow([r.get(c) for c in t["columns"]])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{chart_id}.csv"'})
    return p


@router.get("/drilldown")
def drilldown(type: str, key: str, season: Optional[str] = None, year_from: Optional[int] = None, year_to: Optional[int] = None, format: Optional[str] = None):
    """Underlying records behind a clicked chart element: country (NOC), sport, games, athlete."""
    par: dict = {}
    w = ""
    if season in ("summer", "winter"):
        w += " AND season=:season"; par["season"] = season
    if year_from:
        w += " AND year>=:yf"; par["yf"] = year_from
    if year_to:
        w += " AND year<=:yt"; par["yt"] = year_to
    if type == "country":
        d = df(f"SELECT games_id, country_name, official_rank, gold, silver, bronze, total, athletes, sports FROM gold_country_medals WHERE noc_code=:k {w} ORDER BY year, season", k=key.upper(), **par)
        title = f"Medal-table results for {key.upper()}"
    elif type == "sport":
        d = df(f"SELECT games_id, sport_name, athletes, nocs, events, medal_awards, female_athletes, male_athletes FROM gold_sport_performance WHERE sport_name=:k {w} ORDER BY year, season", k=key, **par)
        title = f"{key} by Games"
    elif type == "games":
        d = df("SELECT noc_code, country_name, official_rank, gold, silver, bronze, total, athletes FROM gold_country_medals WHERE games_id=:k ORDER BY official_rank", k=key)
        title = f"Medal table, {key.replace('_', ' ')}"
    elif type == "athlete":
        d = df("SELECT p.games_id, p.sport_name, p.event_name, p.noc_code, p.age, p.medal FROM silver_participations p WHERE p.athlete_id=:k ORDER BY p.year", k=int(key) if str(key).isdigit() else -1)
        title = f"Participations of athlete {key}"
    else:
        raise HTTPException(400, "type must be country, sport, games or athlete")
    if d.empty:
        raise HTTPException(404, "no records for this selection")
    if format == "csv":
        buf = io.StringIO()
        d.to_csv(buf, index=False)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{type}_{key}.csv"'})
    return {"title": title, "columns": list(d.columns), "rows": json.loads(d.head(500).to_json(orient="records")), "total": int(len(d))}


@router.get("/coverage")
def coverage():
    if not COVERAGE.exists():
        raise HTTPException(404, "coverage report not generated yet - run scripts/build_viz_coverage.py")
    return json.loads(COVERAGE.read_text(encoding="utf-8"))
