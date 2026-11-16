"""Olympic Sports Intelligence Platform API (Phase 10). Reads the Gold/Silver layers and stored analytics; aggregation happens here,
never in the browser. All list endpoints paginate; filters are parameterised; heavy analytics payloads are cached by their generation time."""
from __future__ import annotations

import csv
import io
import json
import re
import time
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from backend.database.session import engine

router = APIRouter()
LOGO_DIR_HINT = "/assets/logos"  # served from frontend/public (see scripts/sync_assets.py)


# ------------------------------------------------------------------ helpers
def rows(sql: str, **p) -> list[dict]:
    with engine.connect() as con:
        return [dict(r) for r in con.execute(text(sql), p).mappings().all()]


def one(sql: str, **p) -> Optional[dict]:
    r = rows(sql, **p)
    return r[0] if r else None


def scalar(sql: str, **p):
    with engine.connect() as con:
        return con.execute(text(sql), p).scalar()


def page(sql_count: str, sql_rows: str, page_no: int, size: int, **p) -> dict:
    total = scalar(sql_count, **p)
    return {"total": total, "page": page_no, "page_size": size, "rows": rows(sql_rows + " LIMIT :_lim OFFSET :_off", **p, _lim=size, _off=(max(page_no, 1) - 1) * size)}


_cache: dict[str, tuple[float, Any]] = {}


def cached(key: str, fn, ttl: int = 120):
    now = time.time()
    if key in _cache and now - _cache[key][0] < ttl:
        return _cache[key][1]
    v = fn()
    _cache[key] = (now, v)
    return v


def analytics(module: str, key: Optional[str] = None):
    if key:
        r = one("SELECT title, question, payload_json, generated_at FROM analytics_results WHERE module=:m AND key=:k", m=module, k=key)
        if not r:
            raise HTTPException(404, f"analysis {module}/{key} has not been generated (run scripts/run_analytics.py)")
        return cached(f"a:{module}:{key}:{r['generated_at']}", lambda: {"module": module, "key": key, "title": r["title"], "question": r["question"], "generated_at": r["generated_at"], "data": json.loads(r["payload_json"])}, 600)
    return rows("SELECT module, key, title, question, generated_at FROM analytics_results WHERE module=:m ORDER BY key", m=module)


def csv_response(data: list[dict], name: str) -> StreamingResponse:
    buf = io.StringIO()
    if data:
        w = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


def season_ok(s: Optional[str]):
    if s and s.lower() not in ("summer", "winter"):
        raise HTTPException(422, "season must be summer or winter")
    return s.lower() if s else None


def fmt(data: list[dict], format: Optional[str], name: str):
    return csv_response(data, name) if format == "csv" else None


# ------------------------------------------------------------------ overview / games
@router.get("/overview", tags=["overview"])
def overview(games_id: Optional[str] = None):
    def build():
        g = analytics("eda", "A_global_overview")["data"]
        sel = games_id or "2024_summer"
        ed = one("SELECT e.*, g.official_edition_name, g.opening_date, g.closing_date FROM gold_edition_performance e JOIN games g USING(games_id) WHERE e.games_id=:g", g=sel)
        return {"kpis": {k: g[k] for k in ("editions", "unique_athletes", "participations", "nocs", "sports", "events", "medal_awards", "team_matches", "disciplines")},
                "selected_edition": ed, "participation_growth": g["participation_growth"],
                "season_comparison": rows("SELECT * FROM gold_season_comparison"),
                "gender_progression": rows("SELECT games_id, year, season, female_share, male_athletes, female_athletes FROM gold_edition_performance ORDER BY year, season"),
                "top_countries": rows("SELECT noc_code, historical_name, gold, silver, bronze, total_medals FROM gold_country_participation_history WHERE total_medals>0 ORDER BY gold DESC, total_medals DESC LIMIT 12"),
                "top_sports": rows("SELECT sport_name, season, SUM(athletes) athletes FROM gold_sport_performance GROUP BY sport_name, season ORDER BY athletes DESC LIMIT 12"),
                "timeline": rows("SELECT games_id, year, season, host_city, host_country FROM gold_edition_performance ORDER BY year, season")}
    return cached(f"overview:{games_id}", build, 300)


@router.get("/games", tags=["games"])
def games(season: Optional[str] = None, format: Optional[str] = None, include_upcoming: bool = False):
    season = season_ok(season)
    data = rows("""SELECT e.games_id, e.year, e.season, e.host_city, e.host_country, e.host_noc, e.athletes, e.nocs, e.sports, e.events, e.medal_awards, e.female_share,
                   e.opening_date, e.closing_date, g.official_edition_name, g.olympedia_url, g.wikipedia_url,
                   (SELECT group_concat(noc_code || ':' || gold || '-' || silver || '-' || bronze, ' ') FROM (SELECT noc_code, gold, silver, bronze FROM gold_country_medals c WHERE c.games_id=e.games_id ORDER BY rank_by_gold_silver_bronze, total DESC LIMIT 3)) AS podium_preview
                   FROM gold_edition_performance e JOIN games g USING(games_id) WHERE (:s IS NULL OR e.season=:s) ORDER BY e.year, e.season""", s=season)
    if include_upcoming:   # planned Games (no results yet): identity fields only, flagged upcoming; the host NOC comes from an earlier edition held in the same country
        data = [{**r, "upcoming": False} for r in data] + [{**r, "upcoming": True} for r in rows("""SELECT g.games_id, g.year, g.season, g.host_city, g.host_country,
                   (SELECT e.host_noc FROM gold_edition_performance e WHERE e.host_country=g.host_country LIMIT 1) host_noc, g.opening_date, g.closing_date, g.official_edition_name
                   FROM games g WHERE g.year>2026 AND (:s IS NULL OR g.season=:s) ORDER BY g.year""", s=season)]
    return fmt(data, format, "games") or data


@router.get("/games/{games_id}", tags=["games"])
def game(games_id: str, sport_id: Optional[int] = None, noc: Optional[str] = None):
    ed = one("SELECT e.*, g.official_edition_name, g.olympedia_url, g.wikipedia_url, g.official_logo FROM gold_edition_performance e JOIN games g USING(games_id) WHERE e.games_id=:g", g=games_id)
    if not ed:
        raise HTTPException(404, "unknown games_id")
    return {"edition": ed,
            "medal_table": rows("SELECT * FROM gold_country_medals WHERE games_id=:g AND (:n IS NULL OR noc_code=:n) ORDER BY rank_by_gold_silver_bronze, total DESC", g=games_id, n=noc.upper() if noc else None),
            "sports": rows("SELECT * FROM gold_sport_performance WHERE games_id=:g AND (:s IS NULL OR sport_id=:s) ORDER BY athletes DESC", g=games_id, s=sport_id),
            "gender": rows("SELECT sport_name, gender, athletes FROM gold_gender_participation WHERE games_id=:g", g=games_id),
            "venues": rows("SELECT venue_name, city, country, sport, capacity, latitude, longitude, venue_image, source_url FROM venues WHERE games_id=:g ORDER BY venue_name", g=games_id),
            "records": rows("SELECT * FROM gold_records WHERE games_id=:g", g=games_id),
            "host": one("SELECT * FROM gold_host_performance WHERE games_id=:g", g=games_id),
            "participating_nocs": rows("SELECT noc_code, COUNT(DISTINCT athlete_id) athletes FROM silver_participations WHERE games_id=:g GROUP BY noc_code ORDER BY athletes DESC", g=games_id)}


# ------------------------------------------------------------------ countries
@router.get("/countries", tags=["countries"])
def countries(q: Optional[str] = None, continent: Optional[str] = None, sort: str = "total_medals", order: str = "desc", page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=300), format: Optional[str] = None):
    if sort not in ("total_medals", "gold", "appearances", "athletes", "historical_name", "first_year"):
        raise HTTPException(422, "bad sort")
    o = "DESC" if order.lower() == "desc" else "ASC"
    where = "WHERE appearances>0 AND (:q IS NULL OR LOWER(historical_name) LIKE :q OR noc_code=:qu) AND (:c IS NULL OR continent=:c)"
    p = dict(q=f"%{q.lower()}%" if q else None, qu=q.upper() if q else None, c=continent)
    if format == "csv":
        return csv_response(rows(f"SELECT * FROM gold_country_participation_history {where} ORDER BY {sort} {o}", **p), "countries")
    return page(f"SELECT COUNT(*) FROM gold_country_participation_history {where}", f"SELECT * FROM gold_country_participation_history {where} ORDER BY {sort} {o}, noc_code", page_no, page_size, **p)


@router.get("/countries/compare", tags=["countries"])
def compare_countries(nocs: str):
    ids = [n.strip().upper() for n in nocs.split(",") if n.strip()][:6]
    if len(ids) < 2:
        raise HTTPException(422, "give at least two NOC codes")
    return {n: rows("SELECT year, season, games_id, gold, silver, bronze, total, athletes, sports, official_rank FROM gold_country_medals WHERE noc_code=:n ORDER BY year, season", n=n) for n in ids}


@router.get("/countries/{noc_code}", tags=["countries"])
def country(noc_code: str):
    n = noc_code.upper()
    h = one("SELECT * FROM gold_country_participation_history WHERE noc_code=:n", n=n)
    if not h:
        raise HTTPException(404, "unknown NOC")
    return {"profile": h, "medals_by_edition": rows("SELECT year, season, games_id, gold, silver, bronze, total, athletes, sports, official_rank, is_host, medal_share FROM gold_country_medals WHERE noc_code=:n ORDER BY year, season", n=n),
            "participation_by_edition": rows("SELECT games_id, year, season, COUNT(DISTINCT athlete_id) athletes, COUNT(DISTINCT sport_id) sports FROM silver_participations WHERE noc_code=:n GROUP BY games_id ORDER BY year, season", n=n),
            "medals_by_sport": rows("SELECT s.sport_name, SUM(a.medal_type='Gold') gold, SUM(a.medal_type='Silver') silver, SUM(a.medal_type='Bronze') bronze, COUNT(*) total FROM silver_medal_awards a JOIN sports s USING(sport_id) WHERE a.noc_code=:n GROUP BY s.sport_name ORDER BY total DESC LIMIT 25", n=n),
            "summer_vs_winter": rows("SELECT season, SUM(gold) gold, SUM(silver) silver, SUM(bronze) bronze, SUM(total) total FROM gold_country_medals WHERE noc_code=:n GROUP BY season", n=n),
            "noc_info": one("SELECT noc_code, historical_name, continent, iso_alpha3, flag_url, is_unified_or_neutral, notes FROM historical_nocs WHERE noc_code=:n", n=n)}


# ------------------------------------------------------------------ athletes
@router.get("/athletes", tags=["athletes"])
def athletes(q: Optional[str] = None, noc: Optional[str] = None, sport: Optional[str] = None, gender: Optional[str] = None, games_id: Optional[str] = None,
             medal: Optional[str] = Query(None, description="any|gold|silver|bronze"), sort: str = "medals", page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=200), format: Optional[str] = None):
    if sort not in ("medals", "gold", "games_count", "career_span_years", "full_name"):
        raise HTTPException(422, "bad sort")
    if gender and gender.upper() not in ("M", "F"):
        raise HTTPException(422, "gender must be M or F")
    if medal and medal.lower() not in ("any", "gold", "silver", "bronze"):
        raise HTTPException(422, "bad medal filter")
    conds, p = ["1=1"], {}
    if q:
        conds.append("LOWER(c.full_name) LIKE :q"); p["q"] = f"%{q.lower()}%"
    if gender:
        conds.append("c.gender=:g"); p["g"] = gender.upper()
    if noc:
        conds.append("(',' || c.nocs || ',') LIKE :noc"); p["noc"] = f"%,{noc.upper()},%"
    if sport:
        conds.append("c.sports LIKE :sp"); p["sp"] = f"%{sport}%"
    if games_id:
        conds.append("EXISTS (SELECT 1 FROM silver_participations x WHERE x.athlete_id=c.athlete_id AND x.games_id=:gid)"); p["gid"] = games_id
    if medal:
        conds.append({"any": "c.medals>0", "gold": "c.gold>0", "silver": "c.silver>0", "bronze": "c.bronze>0"}[medal.lower()])
    w = " AND ".join(conds)
    o = "c.full_name ASC" if sort == "full_name" else f"c.{sort} DESC, c.gold DESC"
    if format == "csv":
        return csv_response(rows(f"SELECT c.* FROM gold_athlete_career c WHERE {w} ORDER BY {o} LIMIT 20000", **p), "athletes")
    return page(f"SELECT COUNT(*) FROM gold_athlete_career c WHERE {w}", f"SELECT c.* FROM gold_athlete_career c WHERE {w} ORDER BY {o}", page_no, page_size, **p)


@router.get("/athletes/compare", tags=["athletes"])
def compare_athletes(ids: str):
    idl = [int(i) for i in re.findall(r"\d+", ids)][:5]
    if len(idl) < 2:
        raise HTTPException(422, "give at least two athlete ids")
    return [{"career": one("SELECT * FROM gold_athlete_career WHERE athlete_id=:i", i=i),
             "timeline": rows("SELECT games_id, year, sport_name, event_name, noc_code, age, medal FROM silver_participations WHERE athlete_id=:i ORDER BY year", i=i)} for i in idl]


def athlete_performances(athlete_id: int) -> list[dict]:
    """Every recorded finish (heats, finals, medals) of one athlete, from the Olympedia per-athlete results via the id map."""
    r = one("SELECT identity_key FROM silver_athletes WHERE athlete_id=:i", i=athlete_id)
    if not r or not r["identity_key"] or not str(r["identity_key"]).startswith("athlete_events:"):
        return []
    m = one("SELECT olympedia_athlete_id FROM athlete_id_map WHERE kaggle_id=:k", k=str(r["identity_key"]).split(":", 1)[1])
    if not m:
        return []
    return rows("SELECT games_id, sport, event, team, position, medal FROM olympedia_athlete_results WHERE athlete_id=:o ORDER BY games_id, event", o=m["olympedia_athlete_id"])


@router.get("/athletes/{athlete_id}", tags=["athletes"])
def athlete(athlete_id: int):
    a = one("SELECT a.*, c.games_count, c.first_year, c.last_year, c.gold, c.silver, c.bronze, c.medals, c.nocs, c.sports FROM silver_athletes a LEFT JOIN gold_athlete_career c USING(athlete_id) WHERE a.athlete_id=:i", i=athlete_id)
    if not a:
        raise HTTPException(404, "unknown athlete")
    return {"athlete": a, "participations": rows("SELECT games_id, year, season, sport_name, event_name, noc_code, age, medal FROM silver_participations WHERE athlete_id=:i ORDER BY year, event_name", i=athlete_id),
            "performances": athlete_performances(athlete_id),
            "photo": None, "photo_note": "No athlete photographs have been collected (licensing/asset phase not run)."}


# ------------------------------------------------------------------ sports / events / results
@router.get("/sports", tags=["sports"])
def sports(season: Optional[str] = None):
    season = season_ok(season)
    return rows("""SELECT s.sport_id, s.sport_name, s.season, s.first_appearance, s.last_appearance, s.number_of_events, s.mens_events, s.womens_events, s.mixed_events, s.is_discontinued,
                   (SELECT COUNT(DISTINCT games_id) FROM gold_sport_performance p WHERE p.sport_id=s.sport_id) editions,
                   (SELECT SUM(athletes) FROM gold_sport_performance p WHERE p.sport_id=s.sport_id) athlete_participations,
                   (SELECT COUNT(DISTINCT noc_code) FROM silver_medal_awards a WHERE a.sport_id=s.sport_id) medal_winning_nocs
                   FROM sports s WHERE (:s IS NULL OR s.season=:s) ORDER BY s.sport_name""", s=season)


@router.get("/sports/{sport_id}", tags=["sports"])
def sport(sport_id: int):
    s = one("SELECT * FROM sports WHERE sport_id=:i", i=sport_id)
    if not s:
        raise HTTPException(404, "unknown sport")
    return {"sport": s, "by_edition": rows("SELECT games_id, year, athletes, nocs, events, medal_awards, female_athletes, male_athletes FROM gold_sport_performance WHERE sport_id=:i ORDER BY year", i=sport_id),
            "medals_by_noc": rows("SELECT noc_code, SUM(medal_type='Gold') gold, SUM(medal_type='Silver') silver, SUM(medal_type='Bronze') bronze, COUNT(*) total FROM silver_medal_awards WHERE sport_id=:i GROUP BY noc_code ORDER BY gold DESC, total DESC LIMIT 20", i=sport_id),
            "disciplines": rows("SELECT discipline_id, discipline_name, first_appearance, last_appearance FROM disciplines WHERE sport_id=:i", i=sport_id)}


@router.get("/events", tags=["events"])
def events(games_id: Optional[str] = None, sport_id: Optional[int] = None, gender: Optional[str] = None, q: Optional[str] = None, page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=300)):
    w = "WHERE (:g IS NULL OR e.games_id=:g) AND (:s IS NULL OR e.sport_id=:s) AND (:q IS NULL OR LOWER(e.event_name) LIKE :q) AND (:gen IS NULL OR e.event_gender IN (SELECT v FROM (SELECT 'M' v WHERE :gen='M' UNION SELECT 'Men' WHERE :gen='M' UNION SELECT 'F' WHERE :gen='F' UNION SELECT 'Women' WHERE :gen='F' UNION SELECT 'X' WHERE :gen='X' UNION SELECT 'Mixed' WHERE :gen='X')))"
    p = dict(g=games_id, s=sport_id, q=f"%{q.lower()}%" if q else None, gen=gender.upper() if gender else None)
    return page(f"SELECT COUNT(*) FROM events e {w}", f"SELECT e.event_id, e.games_id, e.sport_id, e.discipline_id, e.event_name, e.event_gender FROM events e {w} ORDER BY e.games_id, e.event_name", page_no, page_size, **p)


@router.get("/results", tags=["results"])
def results(games_id: Optional[str] = None, sport: Optional[str] = None, event: Optional[str] = None, athlete: Optional[str] = None, noc: Optional[str] = None,
            medal: Optional[str] = None, position: Optional[str] = None, season: Optional[str] = None, sort: str = "year", order: str = "desc",
            page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=500), format: Optional[str] = None):
    season = season_ok(season)
    if sort not in ("year", "sport_name", "event_name", "noc", "medal", "competitor"):
        raise HTTPException(422, "bad sort")
    w = ("WHERE (:g IS NULL OR r.games_id=:g) AND (:sp IS NULL OR LOWER(r.sport_name) LIKE :sp) AND (:ev IS NULL OR LOWER(r.event_name) LIKE :ev) AND (:ath IS NULL OR LOWER(r.competitor) LIKE :ath) "
         "AND (:noc IS NULL OR r.noc=:noc) AND (:m IS NULL OR r.medal=:m) AND (:pos IS NULL OR r.position=:pos) AND (:se IS NULL OR r.season=:se)")
    p = dict(g=games_id, sp=f"%{sport.lower()}%" if sport else None, ev=f"%{event.lower()}%" if event else None, ath=f"%{athlete.lower()}%" if athlete else None,
             noc=noc.upper() if noc else None, m=medal.capitalize() if medal else None, pos=position, se=season)
    cols = "r.games_id, r.year, r.season, r.sport_name, r.event_name, r.position, r.competitor, r.noc, r.medal, r.result_text, r.result_value, r.result_unit, r.source_url"
    o = f"ORDER BY r.{sort} {'DESC' if order.lower() == 'desc' else 'ASC'}, r.event_name"
    if format == "csv":
        return csv_response(rows(f"SELECT {cols} FROM gold_event_results r {w} {o} LIMIT 50000", **p), "results")
    return page(f"SELECT COUNT(*) FROM gold_event_results r {w}", f"SELECT {cols} FROM gold_event_results r {w} {o}", page_no, page_size, **p)


@router.get("/results/phases", tags=["results"])
def result_phases(games_id: Optional[str] = None, sport: Optional[str] = None, event: Optional[str] = None, athlete: Optional[str] = None, noc: Optional[str] = None,
                  page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=500), format: Optional[str] = None):
    """Earlier rounds (heats, quarter/semi-finals, pools ...) of every event, from the same Olympedia result pages."""
    w = ("WHERE (:g IS NULL OR r.games_id=:g) AND (:sp IS NULL OR LOWER(r.sport_name) LIKE :sp) AND (:ev IS NULL OR LOWER(r.event_name) LIKE :ev) "
         "AND (:ath IS NULL OR LOWER(r.competitor) LIKE :ath) AND (:noc IS NULL OR r.noc=:noc)")
    p = dict(g=games_id, sp=f"%{sport.lower()}%" if sport else None, ev=f"%{event.lower()}%" if event else None, ath=f"%{athlete.lower()}%" if athlete else None, noc=noc.upper() if noc else None)
    cols = "r.games_id, r.year, r.season, r.sport_name, r.event_name, r.phase, r.position, r.competitor, r.noc, r.result_text, r.result_value, r.result_unit, r.source_url"
    if format == "csv":
        return csv_response(rows(f"SELECT {cols} FROM gold_event_phases r {w} ORDER BY r.year DESC, r.event_name LIMIT 50000", **p), "result_phases")
    return page(f"SELECT COUNT(*) FROM gold_event_phases r {w}", f"SELECT {cols} FROM gold_event_phases r {w} ORDER BY r.year DESC, r.event_name, r.phase", page_no, page_size, **p)


# ------------------------------------------------------------------ medals
@router.get("/medals", tags=["medals"])
def medals(games_id: Optional[str] = None, season: Optional[str] = None, sport_id: Optional[int] = None, view: str = "alltime", limit: int = Query(60, le=300), format: Optional[str] = None):
    """Tie-aware ranking: RANK() over (gold, silver, bronze) - NOCs with identical G/S/B share a rank."""
    season = season_ok(season)
    if view == "alltime":
        data = rows("""SELECT RANK() OVER (ORDER BY gold DESC, silver DESC, bronze DESC) AS rank, noc_code, historical_name, gold, silver, bronze, total_medals AS total, appearances, first_medal_games
                       FROM (SELECT h.noc_code, h.historical_name, SUM(c.gold) gold, SUM(c.silver) silver, SUM(c.bronze) bronze, SUM(c.total) total_medals, h.appearances, h.first_medal_games
                             FROM gold_country_medals c JOIN gold_country_participation_history h USING(noc_code) WHERE (:s IS NULL OR c.season=:s) GROUP BY c.noc_code) ORDER BY rank, noc_code LIMIT :l""", s=season, l=limit)
    elif view == "edition":
        if not games_id:
            raise HTTPException(422, "games_id is required for view=edition")
        data = rows("SELECT rank_by_gold_silver_bronze AS rank, noc_code, country_name, gold, silver, bronze, total, official_rank, medal_share, gold_ratio, is_host FROM gold_country_medals WHERE games_id=:g ORDER BY rank, total DESC LIMIT :l", g=games_id, l=limit)
    elif view == "sport":
        data = rows("""SELECT RANK() OVER (ORDER BY gold DESC, silver DESC, bronze DESC) AS rank, noc_code, gold, silver, bronze, total FROM (
                       SELECT noc_code, SUM(medal_type='Gold') gold, SUM(medal_type='Silver') silver, SUM(medal_type='Bronze') bronze, COUNT(*) total FROM silver_medal_awards
                       WHERE (:sp IS NULL OR sport_id=:sp) AND (:g IS NULL OR games_id=:g) GROUP BY noc_code) ORDER BY rank LIMIT :l""", sp=sport_id, g=games_id, l=limit)
    else:
        raise HTTPException(422, "view must be alltime, edition or sport")
    out = fmt(data, format, "medals")
    if out:
        return out
    prog = rows("SELECT year, season, noc_code, total FROM gold_country_medals WHERE noc_code IN (SELECT noc_code FROM gold_country_participation_history ORDER BY total_medals DESC LIMIT 8) ORDER BY year") if view == "alltime" else []
    conc = analytics("stats", "distributions")["data"]["pareto_medals_by_noc"] if view == "alltime" else None
    return {"view": view, "rows": data, "progression_top8": prog, "concentration": conc,
            "note": "Ties share a rank. Country totals = distinct Olympedia event podiums (matches official totals); the Wikipedia tables are stored beside them as a cross-check."}


# ------------------------------------------------------------------ statistics / eda / ml / sports analytics
@router.get("/eda", tags=["analytics"])
def eda_index():
    return analytics("eda")


@router.get("/eda/{key}", tags=["analytics"])
def eda(key: str):
    return analytics("eda", key)


@router.get("/statistics", tags=["statistics"])
def statistics(section: Optional[str] = None):
    if not section:
        return analytics("stats")
    return analytics("stats", section)


@router.get("/statistics/hypothesis-tests", tags=["statistics"])
def hypothesis_tests(family: Optional[str] = None):
    r = rows("SELECT * FROM analytics_hypothesis_tests WHERE (:f IS NULL OR family=:f) ORDER BY test_id", f=family)
    for t in r:
        t["assumptions"] = json.loads(t.pop("assumptions_json") or "{}")
    return r


@router.get("/statistics/regression", tags=["statistics"])
def regression():
    return analytics("stats", "regression")


@router.get("/statistics/time-series", tags=["statistics"])
def time_series():
    return analytics("stats", "time_series")


@router.get("/machine-learning/models", tags=["machine-learning"])
def ml_models():
    reg = analytics("ml", "model_registry")
    ml_a, ml_b = analytics("ml", "medal_prediction")["data"], analytics("ml", "athlete_medal_model")["data"]
    return {"registry": reg["data"], "country_medal_models": ml_a["metrics_all_participating_nocs"], "athlete_models": {k: {m: v for m, v in d.items() if m != "calibration"} for k, d in ml_b["models"].items()},
            "validation": "chronological (expanding window / train<2000, val 2000-07, test>=2008); backtests, not forecasts"}


@router.get("/machine-learning/predictions", tags=["machine-learning"])
def ml_predictions(kind: str = "medal_prediction"):
    if kind not in ("medal_prediction", "athlete_medal_model", "clustering", "sport_specialization"):
        raise HTTPException(422, "kind must be medal_prediction, athlete_medal_model, clustering or sport_specialization")
    return analytics("ml", kind)


@router.get("/sports-analytics", tags=["sports"])
def sports_analytics_index():
    return analytics("sports")


@router.get("/sports-analytics/{key}", tags=["sports"])
def sports_analytics(key: str):
    return analytics("sports", key)


# ------------------------------------------------------------------ team sports / matches / records
@router.get("/team-sports", tags=["team-sports"])
def team_sports(sport: Optional[str] = None, games_id: Optional[str] = None):
    return rows("""SELECT games_id, sport_name, team, noc, played, won, drawn, lost, goals_for, goals_against, goal_diff, points_per_game FROM gold_team_sports
                   WHERE (:s IS NULL OR sport_name=:s) AND (:g IS NULL OR games_id=:g) ORDER BY games_id, sport_name, points_per_game DESC, goal_diff DESC""", s=sport, g=games_id)


@router.get("/matches", tags=["team-sports"])
def matches(games_id: Optional[str] = None, sport: Optional[str] = None, team: Optional[str] = None, stage: Optional[str] = None, page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=300), format: Optional[str] = None):
    w = "WHERE (:g IS NULL OR games_id=:g) AND (:s IS NULL OR sport_name=:s) AND (:t IS NULL OR LOWER(home_team) LIKE :t OR LOWER(away_team) LIKE :t) AND (:st IS NULL OR LOWER(stage) LIKE :st) AND home_team IS NOT NULL"
    p = dict(g=games_id, s=sport, t=f"%{team.lower()}%" if team else None, st=f"%{stage.lower()}%" if stage else None)
    cols = "result_id, games_id, sport_name, event_name, stage, match_date, location, home_team, home_noc, home_score, away_team, away_noc, away_score, period_scores, source_url"
    if format == "csv":
        return csv_response(rows(f"SELECT {cols} FROM olympedia_matches {w} ORDER BY games_id, match_date LIMIT 50000", **p), "matches")
    return page(f"SELECT COUNT(*) FROM olympedia_matches {w}", f"SELECT {cols} FROM olympedia_matches {w} ORDER BY games_id, match_date", page_no, page_size, **p)


@router.get("/records", tags=["records"])
def records(level: Optional[str] = None, games_id: Optional[str] = None, page_no: int = Query(1, alias="page"), page_size: int = Query(100, le=500)):
    w = "WHERE (:l IS NULL OR record_level=:l) AND (:g IS NULL OR games_id=:g)"
    return {"records": page(f"SELECT COUNT(*) FROM gold_records {w}", f"SELECT * FROM gold_records {w} ORDER BY games_id DESC", page_no, page_size, l=level, g=games_id),
            "most_decorated": rows("SELECT athlete_id, full_name, gold, silver, bronze, medals, games_count FROM gold_athlete_career ORDER BY medals DESC, gold DESC LIMIT 15"),
            "most_successful_countries": rows("SELECT noc_code, historical_name, gold, silver, bronze, total_medals FROM gold_country_participation_history ORDER BY gold DESC LIMIT 15"),
            "longest_careers": rows("SELECT athlete_id, full_name, career_span_years, first_year, last_year FROM gold_athlete_career ORDER BY career_span_years DESC LIMIT 15"),
            "most_appearances": rows("SELECT athlete_id, full_name, games_count FROM gold_athlete_career ORDER BY games_count DESC, medals DESC LIMIT 15")}


# ------------------------------------------------------------------ data quality / engineering
@router.get("/data-quality", tags=["data-engineering"])
def data_quality():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]

    def csv_rows(p):
        f = root / p
        if not f.exists():
            return []
        with f.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    return {"validation": csv_rows("reports/quality/validation_results.csv"), "findings": csv_rows("reports/data_quality/quality_findings.csv"), "relationships": csv_rows("reports/data_inventory/relationships.csv"),
            "completeness_matrix": csv_rows("reports/data_completeness/edition_dataset_matrix.csv"), "missing": csv_rows("reports/data_completeness/missing_edition_datasets.csv"),
            "reconciliation": rows("SELECT games_id, COUNT(*) nocs, SUM(wikipedia_total IS NULL) not_in_wikipedia, SUM(reconciliation_diff=0) exact, SUM(ABS(reconciliation_diff)<=2) within2, SUM(total) olympedia_total, SUM(wikipedia_total) wikipedia_total FROM gold_country_medals GROUP BY games_id ORDER BY games_id")}


def _table_names() -> set:
    """Names of all warehouse tables."""
    try:  # slim deployment DB: the full warehouse's table list is recorded at build time
        return {r["name"] for r in rows("SELECT name FROM _warehouse_tables")}
    except Exception:  # noqa: BLE001
        pass
    return {r["name"] for r in rows("SELECT name FROM sqlite_master WHERE type='table'")}


def _count(t: str):
    """Live row count; the slim deployment DB keeps exact counts of dropped staging tables in _table_counts."""
    try:
        return scalar(f"SELECT COUNT(*) FROM {t}")
    except Exception:  # noqa: BLE001
        return scalar("SELECT n FROM _table_counts WHERE name = :t", t=t)


@router.get("/data-engineering/pipeline-status", tags=["data-engineering"])
def pipeline_status():
    inv = rows("SELECT dataset, rows, columns, missing_cells_pct FROM (SELECT name dataset FROM sqlite_master WHERE type='table') LEFT JOIN (SELECT 1 rows, 1 columns, 1 missing_cells_pct) ON 0") if False else []
    names = _table_names()
    layers = {"bronze_tables": sum(1 for n in names if n.startswith(("src_", "olympedia_", "wikipedia_"))),
              "silver_tables": sum(1 for n in names if n.startswith("silver_")), "gold_tables": sum(1 for n in names if n.startswith("gold_") and n != "gold_build_state")}
    counts = {t: _count(t) for t in ("athletes", "athlete_participations", "silver_participations", "gold_athlete_career", "gold_country_medals", "event_results", "gold_event_results", "olympedia_standings", "olympedia_matches")}
    return {"layers": layers, "row_counts": counts, "runs": rows("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 20"),
            "gold_build_state": rows("SELECT COUNT(*) games, MAX(built_at) last_built FROM gold_build_state"),
            "duplicates": rows("SELECT dataset, duplicate_rows_excluding_ids dup FROM (SELECT 'see reports/data_inventory/dataset_inventory.csv' dataset, 0 duplicate_rows_excluding_ids) WHERE 0"),
            "analytics_generated": rows("SELECT module, COUNT(*) results, MAX(generated_at) last FROM analytics_results GROUP BY module"),
            "tests_passed_last": None, "last_validation": rows("SELECT generated_at, metrics_json FROM data_quality_reports WHERE report_type='validation' ORDER BY report_id DESC LIMIT 1")}


# ------------------------------------------------------------------ live, filterable statistics (computed on demand on the backend)
@router.get("/statistics/explore", tags=["statistics"])
def statistics_explore(season: Optional[str] = None, gender: Optional[str] = None, sport: Optional[str] = None, noc: Optional[str] = None, games_id: Optional[str] = None):
    """Athlete-age statistics for any edition / sport / country / gender slice, with a live medalist-vs-others test."""
    import numpy as np
    import pandas as pd
    from scipy import stats as st

    season = season_ok(season)
    if gender and gender.upper() not in ("M", "F"):
        raise HTTPException(422, "gender must be M or F")
    conds, p = ["age IS NOT NULL"], {}
    for col, key, val in (("season", "s", season), ("gender", "g", gender.upper() if gender else None), ("sport_name", "sp", sport), ("noc_code", "n", noc.upper() if noc else None), ("games_id", "gid", games_id)):
        if val:
            conds.append(f"{col}=:{key}")
            p[key] = val
    df = pd.DataFrame(rows(f"SELECT age, is_medalist FROM silver_participations WHERE {' AND '.join(conds)}", **p))
    if df.empty or len(df) < 5:
        return {"n": int(len(df)), "message": "Not enough athletes for this selection (need at least 5 with a recorded age).", "filters": {"season": season, "gender": gender, "sport": sport, "noc": noc, "games_id": games_id}}
    a = df.age.astype(float)
    desc = {"n": int(len(a)), "mean": a.mean(), "median": a.median(), "mode": float(a.mode().iloc[0]), "min": a.min(), "max": a.max(), "range": a.max() - a.min(), "variance": a.var(ddof=1), "std": a.std(ddof=1),
            "q1": a.quantile(.25), "q3": a.quantile(.75), "iqr": a.quantile(.75) - a.quantile(.25), "p5": a.quantile(.05), "p95": a.quantile(.95),
            "skewness": float(st.skew(a, bias=False)), "excess_kurtosis": float(st.kurtosis(a, bias=False)), "cv": a.std(ddof=1) / a.mean()}
    hist, edges = np.histogram(a, bins=range(int(a.min()) - int(a.min()) % 2, int(a.max()) + 3, 2))
    out = {"n": int(len(a)), "filters": {"season": season, "gender": gender, "sport": sport, "noc": noc, "games_id": games_id}, "descriptive": desc,
           "histogram": [{"age": int(e), "count": int(c)} for e, c in zip(edges[:-1], hist)], "medal_rate": float(df.is_medalist.mean())}
    m, o = a[df.is_medalist == 1].values, a[df.is_medalist == 0].values
    if len(m) >= 5 and len(o) >= 5:
        mw = st.mannwhitneyu(m, o)
        wt = st.ttest_ind(m, o, equal_var=False)
        sp_ = np.sqrt(((len(m) - 1) * m.var(ddof=1) + (len(o) - 1) * o.var(ddof=1)) / (len(m) + len(o) - 2))
        diff = m.mean() - o.mean()
        se = np.sqrt(m.var(ddof=1) / len(m) + o.var(ddof=1) / len(o))
        out["medalist_vs_others"] = {"test": "Mann-Whitney U (Welch t shown)", "n_medalists": int(len(m)), "n_others": int(len(o)), "mean_medalists": float(m.mean()), "mean_others": float(o.mean()), "mean_difference": float(diff),
                                      "ci95_mean_difference": [float(diff - 1.96 * se), float(diff + 1.96 * se)], "u_statistic": float(mw.statistic), "p_value": float(mw.pvalue), "welch_t": float(wt.statistic), "welch_p": float(wt.pvalue),
                                      "cohens_d": float(diff / sp_), "rank_biserial": float(1 - 2 * mw.statistic / (len(m) * len(o))),
                                      "note": "Participations are not independent (athletes repeat). Descriptive for this slice, not a confirmatory test."}
    else:
        out["medalist_vs_others"] = None
    return out
