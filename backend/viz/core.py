"""Visualization registry + helpers.

Every chart is a registered builder: `@chart(id, section, page, name, kind, dataset, source, purpose, filters, alternatives)` over a function
`fn(ctx) -> payload`. Builders only read the warehouse (Gold/Silver layers, stored analytics) - nothing is simulated. A builder that cannot be
satisfied by the collected data raises `Unavailable(reason)`, which the coverage report records as "unavailable".

Payload contract (consumed by frontend/src/viz):
  {id, title, kind, alternatives[], axes{x,y}, data{...kind specific...}, table{columns,rows}, interpretation, notes[], drill{...}, filters_applied{}}
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from backend.analytics.store import DB, _clean
from backend.database.session import engine

SECTIONS = {
    1: "Historical and time-series",
    2: "Country and medal",
    3: "Athlete",
    4: "Sports and events",
    5: "Statistical library",
    6: "Machine learning",
    7: "Team sports",
    8: "Data engineering",
}
MEDAL_COLORS = {"Gold": "#D4AF37", "Silver": "#9AA3AF", "Bronze": "#CD7F32"}


class Unavailable(Exception):
    """Raised by a builder when the collected data cannot support the chart (reason is shown to the user)."""


@dataclass
class Spec:
    id: str
    section: int
    page: str
    name: str
    kind: str
    dataset: str
    source: str
    purpose: str
    filters: tuple = ()
    alternatives: tuple = ()
    fn: Optional[Callable] = None

    @property
    def endpoint(self) -> str:
        return f"/api/viz/chart/{self.id}"

    def meta(self) -> dict:
        return {"id": self.id, "section": self.section, "section_name": SECTIONS[self.section], "page": self.page, "name": self.name, "kind": self.kind,
                "alternatives": list(self.alternatives), "dataset": self.dataset, "source_table": self.source, "purpose": self.purpose,
                "filters": list(self.filters), "endpoint": self.endpoint}


REGISTRY: dict[str, Spec] = {}


# views the frontend can switch to for the same data (XY variants + donut/treemap adapters + the data table); anything else is not offered
SUPPORTED_ALTERNATIVES = {"line", "area", "bar", "stacked", "grouped", "percent", "step", "stream", "donut", "treemap", "table"}


def chart(id: str, section: int, page: str, name: str, kind: str, dataset: str, source: str, purpose: str, filters: tuple = (), alternatives: tuple = ()):
    def deco(fn):
        if id in REGISTRY:
            raise ValueError(f"duplicate chart id {id}")
        REGISTRY[id] = Spec(id, section, page, name, kind, dataset, source, purpose, tuple(filters), tuple(a for a in alternatives if a in SUPPORTED_ALTERNATIVES), fn)
        return fn
    return deco


# ------------------------------------------------------------------------------------------------------------------ filters / context
class Ctx:
    """Request filters. Chart builders decide which ones they honour (declared in the registry)."""

    def __init__(self, params: dict | None = None):
        p = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        self.p = p
        self.season = p.get("season") if p.get("season") in ("summer", "winter") else None
        self.year_from = int(p["year_from"]) if str(p.get("year_from", "")).isdigit() else None
        self.year_to = int(p["year_to"]) if str(p.get("year_to", "")).isdigit() else None
        self.noc = (p.get("noc") or "").upper() or None
        self.nocs = [x.strip().upper() for x in str(p.get("nocs", "")).split(",") if x.strip()]
        self.sport = p.get("sport")
        self.games_id = p.get("games_id")
        self.event = p.get("event")
        self.athlete_ids = [int(x) for x in str(p.get("athlete_ids", "")).split(",") if x.strip().isdigit()]
        self.top = max(3, min(int(p["top"]), 60)) if str(p.get("top", "")).isdigit() else None
        self.metric = p.get("metric")
        self.a = (p.get("a") or "").upper() or None
        self.b = (p.get("b") or "").upper() or None

    def where(self, alias: str = "", year: str = "year", season: str = "season") -> tuple[str, dict]:
        """SQL ' AND ...' fragment for season / year range on a table that has year + season columns."""
        a = f"{alias}." if alias else ""
        sql, par = "", {}
        if self.season:
            sql += f" AND {a}{season}=:_season"; par["_season"] = self.season
        if self.year_from is not None:
            sql += f" AND {a}{year}>=:_yf"; par["_yf"] = self.year_from
        if self.year_to is not None:
            sql += f" AND {a}{year}<=:_yt"; par["_yt"] = self.year_to
        return sql, par

    def applied(self) -> dict:
        return {k: v for k, v in self.p.items() if k in ("season", "year_from", "year_to", "noc", "nocs", "sport", "games_id", "event", "athlete_ids", "top", "metric", "a", "b")}


_QCACHE: "OrderedDict[tuple, pd.DataFrame]" = OrderedDict()
# smaller on the serverless host, where the warehouse itself already lives in RAM
_QCACHE_MAX, _QCACHE_MAX_ROWS = (int(os.environ.get("OLY_QCACHE_MAX", 96)), 400_000)


def _db_signature() -> tuple:
    """(mtime, size) of the warehouse file: the query cache is dropped whenever the pipeline rewrites the database."""
    try:
        st = os.stat(DB)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def df(sql: str, **params) -> pd.DataFrame:
    """Run a read-only query. Identical SQL + parameters are served from a small in-memory cache (many charts load the same 250k-row age table);
    callers always get their own copy and the cache is invalidated when the database file changes."""
    key = None
    try:
        key = (sql, tuple(sorted(params.items())), _db_signature())
    except TypeError:  # unhashable parameter: skip the cache
        key = None
    if key is not None and key in _QCACHE:
        _QCACHE.move_to_end(key)
        return _QCACHE[key].copy()
    with engine.connect() as con:
        out = pd.read_sql(text(sql), con, params=params)
    if key is not None and len(out) <= _QCACHE_MAX_ROWS:
        for k in [k for k in _QCACHE if k[2] != key[2]]:
            del _QCACHE[k]
        _QCACHE[key] = out
        while len(_QCACHE) > _QCACHE_MAX:
            _QCACHE.popitem(last=False)
        return out.copy()
    return out


AGE_SQL = "SELECT p.age, p.gender, p.season, p.sport_name, p.is_medalist, p.year FROM silver_participations p WHERE p.age BETWEEN 10 AND 80"


def age_rows(where: str = "", params: dict | None = None) -> pd.DataFrame:
    """The participations that have a recorded age (one shared query, so all age-based charts reuse the same cached 250k rows)."""
    return df(AGE_SQL + where, **(params or {}))


def scalar(sql: str, **params):
    with engine.connect() as con:
        return con.execute(text(sql), params).scalar()


def analytics(module: str, key: str) -> dict:
    with engine.connect() as con:
        r = con.execute(text("SELECT payload_json FROM analytics_results WHERE module=:m AND key=:k"), {"m": module, "k": key}).fetchone()
    if not r:
        raise Unavailable(f"stored analysis {module}/{key} has not been generated (run scripts/run_analytics.py)")
    return json.loads(r[0])


def games_order() -> pd.DataFrame:
    return df("SELECT games_id, year, season FROM games WHERE year BETWEEN 1960 AND 2026 AND year<=2026 AND games_id IN (SELECT games_id FROM gold_edition_performance) ORDER BY year, season")


def noc_names() -> dict:
    d = df("SELECT noc_code, historical_name, iso_alpha3, continent FROM historical_nocs")
    return {r.noc_code: {"name": r.historical_name, "iso3": r.iso_alpha3, "continent": r.continent} for r in d.itertuples()}


def label_games(gid: str) -> str:
    y, s = gid.split("_")
    return f"{y} {s.capitalize()}"


def top_nocs(ctx: Ctx, n: int = 10, by: str = "total") -> list[str]:
    """User-selected NOCs, else the n NOCs with most medals inside the active season / year window."""
    if ctx.nocs:
        return ctx.nocs[:n]
    w, par = ctx.where()
    d = df(f"SELECT noc_code, SUM({by}) m FROM gold_country_medals WHERE 1=1 {w} GROUP BY noc_code ORDER BY m DESC LIMIT {int(n)}", **par)
    return d.noc_code.tolist()


# ------------------------------------------------------------------------------------------------------------------ payload helpers
def table_from(rows: list[dict] | pd.DataFrame, columns: list[str] | None = None, limit: int = 5000) -> dict:
    if isinstance(rows, pd.DataFrame):
        rows = rows.to_dict("records")
    rows = rows[:limit]
    cols = columns or (list(rows[0].keys()) if rows else [])
    return {"columns": cols, "rows": [{c: r.get(c) for c in cols} for r in rows]}


def payload(spec_id: str, kind: str, data: dict, *, axes: dict | None = None, table: dict | None = None, interpretation: str = "", notes: list[str] | None = None,
            alternatives: tuple | list = (), drill: dict | None = None, ctx: Ctx | None = None, title: str | None = None) -> dict:
    spec = REGISTRY.get(spec_id)
    rows = data.get("rows") if isinstance(data, dict) else None
    if table is None and isinstance(rows, list) and rows and isinstance(rows[0], dict):
        table = table_from(rows)
    return _clean({
        "id": spec_id, "title": title or (spec.name if spec else spec_id), "kind": kind, "alternatives": list(alternatives) or list(spec.alternatives if spec else ()),
        "axes": axes or {}, "data": data, "table": table or {"columns": [], "rows": []}, "interpretation": interpretation, "notes": notes or [],
        "drill": drill, "filters_applied": ctx.applied() if ctx else {}, "source": spec.source if spec else "", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })


def wide(d: pd.DataFrame, index: str, columns: str, values: str, fill=None, order_index=None) -> tuple[list[dict], list[str]]:
    """long -> wide rows for multi-series charts. Returns (rows, series_keys)."""
    pv = d.pivot_table(index=index, columns=columns, values=values, aggfunc="sum" if fill == 0 else "first")
    if order_index is not None:
        pv = pv.reindex(order_index)
    if fill is not None:
        pv = pv.fillna(fill)
    pv = pv.reset_index()
    keys = [c for c in pv.columns if c != index]
    return pv.to_dict("records"), [str(k) for k in keys]


def series_defs(keys: list[str], names: dict | None = None, colors: dict | None = None, **extra) -> list[dict]:
    return [{"key": k, "name": (names or {}).get(k, k), **({"color": colors[k]} if colors and k in colors else {}), **extra} for k in keys]


def gini(values) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    v = v[v >= 0]
    if v.sum() == 0:
        return 0.0
    n = len(v)
    return float((2 * np.sum((np.arange(1, n + 1)) * v) / (n * v.sum())) - (n + 1) / n)


def kde(values, n: int = 120, lo=None, hi=None, bw=None):
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 5:
        raise Unavailable("not enough observations for a density estimate")
    lo = v.min() if lo is None else lo
    hi = v.max() if hi is None else hi
    sd = v.std() or 1.0
    h = bw or 1.06 * sd * len(v) ** (-1 / 5)
    xs = np.linspace(lo, hi, n)
    if len(v) > 4000:
        v = np.random.default_rng(0).choice(v, 4000, replace=False)
    d = np.exp(-0.5 * ((xs[:, None] - v[None, :]) / h) ** 2).sum(1) / (len(v) * h * math.sqrt(2 * math.pi))
    return xs, d


def box_stats(v) -> dict:
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return {}
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = v[(v >= lo) & (v <= hi)]
    out = v[(v < lo) | (v > hi)]
    return {"n": int(len(v)), "q1": q1, "median": med, "q3": q3, "min": float(inside.min()), "max": float(inside.max()),
            "mean": float(v.mean()), "outliers": np.round(np.random.default_rng(1).choice(out, 60, replace=False) if len(out) > 60 else out, 3).tolist(), "n_outliers": int(len(out))}


def need_rows(d, what: str = "data"):
    if d is None or (hasattr(d, "empty") and d.empty) or (isinstance(d, (list, dict)) and not d):
        raise Unavailable(f"no {what} for this selection")
    return d


def evaluate(spec: Spec, params: dict | None = None) -> dict:
    ctx = Ctx(params)
    p = spec.fn(ctx)
    p.setdefault("id", spec.id)
    return p
