"""Section 1 - historical and time-series charts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import (MEDAL_COLORS, Ctx, Unavailable, chart, df, need_rows, noc_names, payload, series_defs, table_from, top_nocs, wide)

S = 1
SEASON_COLORS = {"Summer": "#F4A300", "Winter": "#0085C7"}


def _editions(ctx: Ctx, default_season: str | None = None) -> pd.DataFrame:
    c = Ctx({**ctx.p, **({"season": default_season} if default_season and not ctx.season else {})})
    w, par = c.where()
    return need_rows(df(f"SELECT * FROM gold_edition_performance WHERE 1=1 {w} ORDER BY year, season", **par), "editions")


@chart("ts_line_athletes", S, "overview", "Athletes per Games", "xy", "Gold edition performance", "gold_edition_performance",
       "Show how Olympic participation has grown, Summer versus Winter", ("season", "year_range"), ("area", "bar", "step"))
def athletes_per_games(ctx: Ctx):
    e = _editions(ctx)
    e["Season"] = e.season.str.capitalize()
    rows, keys = wide(e, "year", "Season", "athletes")
    parts = []
    for season, g in e.groupby("season"):
        parts.append(f"{season.capitalize()}: {int(g.athletes.iloc[0]):,} athletes in {int(g.year.iloc[0])} to {int(g.athletes.iloc[-1]):,} in {int(g.year.iloc[-1])}")
    return payload("ts_line_athletes", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys, colors=SEASON_COLORS), "variant": "line", "dot": True,
                   "xLabel": "Games year", "yLabel": "Athletes (unique participants)"}, axes={"x": "Games year", "y": "Athletes"}, ctx=ctx,
                   interpretation="; ".join(parts) + ". Summer and Winter Games are different events with different scales, so they are drawn as separate series.",
                   drill={"type": "games", "key": "games_id"})


@chart("ts_multi_index", S, "overview", "Growth of the Games (indexed)", "xy", "Gold edition performance", "gold_edition_performance",
       "Compare growth of athletes, NOCs, sports, events and medals on a common scale (first edition = 100)", ("season", "year_range"), ("area",))
def multi_index(ctx: Ctx):
    e = _editions(ctx, "summer").reset_index(drop=True)
    cols = {"athletes": "Athletes", "nocs": "Nations (NOCs)", "sports": "Sports", "events": "Events", "medal_awards": "Medal awards"}
    out = pd.DataFrame({"year": e.year})
    for k, n in cols.items():
        out[n] = e[k] / e[k].iloc[0] * 100
    rows = out.round(1).to_dict("records")
    last = out.iloc[-1]
    return payload("ts_multi_index", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(list(cols.values())), "variant": "line",
                   "xLabel": "Games year", "yLabel": f"Index (first edition = 100)", "refs": [{"y": 100, "label": "baseline"}]}, axes={"x": "Games year", "y": "Index"}, ctx=ctx,
                   interpretation=f"Indexed to the first edition shown ({int(e.year.iloc[0])} {e.season.iloc[0]}): athletes are at {last['Athletes']:.0f}, events at {last['Events']:.0f}, "
                                  f"nations at {last['Nations (NOCs)']:.0f}. Indexing avoids putting counts of different units on one axis.")


@chart("ts_area_gender", S, "overview", "Male and female athletes per Games", "xy", "Gold edition performance", "gold_edition_performance",
       "Show the shift in gender composition of Olympic participation", ("season", "year_range"), ("percent", "bar", "line"))
def area_gender(ctx: Ctx):
    e = _editions(ctx, "summer")
    rows = [{"year": int(r.year), "Men": int(r.male_athletes), "Women": int(r.female_athletes)} for r in e.itertuples()]
    last = e.iloc[-1]
    return payload("ts_area_gender", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(["Men", "Women"], colors={"Men": "#0085C7", "Women": "#DF0024"}),
                   "variant": "stacked", "xLabel": "Games year", "yLabel": "Athletes"}, axes={"x": "Games year", "y": "Athletes"}, ctx=ctx,
                   interpretation=f"Women were {100 * (last.female_share or 0):.1f}% of athletes in {last.games_id.replace('_', ' ')}. Switch to the percent view to compare shares directly.")


@chart("ts_stream_continent", S, "overview", "Medal awards by continent (stream graph)", "xy", "Gold country medals x NOC continent", "gold_country_medals",
       "Show how the continental distribution of medals changed across Games", ("season", "year_range"), ("area", "percent"))
def stream_continent(ctx: Ctx):
    ctx = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = ctx.where("g")
    d = df(f"SELECT g.year, COALESCE(h.continent,'Unassigned') continent, SUM(g.total) medals FROM gold_country_medals g LEFT JOIN historical_nocs h USING(noc_code) WHERE 1=1 {w} GROUP BY 1,2", **par)
    need_rows(d, "medals")
    rows, keys = wide(d, "year", "continent", "medals", fill=0)
    return payload("ts_stream_continent", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys), "variant": "stream", "xLabel": "Games year", "yLabel": "Medals (stream width)"},
                   axes={"x": "Games year", "y": "Medals"}, ctx=ctx,
                   interpretation="Stream width is the number of medals won by NOCs of each continent in that Games (Summer Games by default, because Summer and Winter alternate in size and would make the stream oscillate; pick Winter with the season filter) (all medals in the official table, team medals counted once per NOC). "
                                  "'Unassigned' covers neutral or dissolved delegations without a continent.")


@chart("ts_moving_avg", S, "overview", "Athletes with 3-edition moving average", "xy", "Gold edition performance", "gold_edition_performance",
       "Separate the long-run trend from edition-to-edition noise", ("season", "year_range"), ("area", "bar"))
def moving_avg(ctx: Ctx):
    e = _editions(ctx, "summer").reset_index(drop=True)
    e["ma"] = e.athletes.rolling(3, min_periods=3).mean()
    rows = [{"year": int(r.year), "Athletes": int(r.athletes), "3-edition moving average": None if pd.isna(r.ma) else round(float(r.ma), 1)} for r in e.itertuples()]
    return payload("ts_moving_avg", "xy", {"x": "year", "xType": "number", "rows": rows, "series": [{"key": "Athletes", "color": "#9AA3AF"}, {"key": "3-edition moving average", "color": "#DF0024"}],
                   "variant": "line", "dot": True, "xLabel": "Games year", "yLabel": "Athletes"}, axes={"x": "Games year", "y": "Athletes"}, ctx=ctx,
                   interpretation="The red line averages each Games with the two before it (needs 3 editions), so the first two Games have no average.")


@chart("ts_rolling_trend", S, "overview", "Rolling trend in female share", "xy", "Gold edition performance", "gold_edition_performance",
       "Show whether the pace of gender-balance change is speeding up or slowing", ("year_range",), ("bar",))
def rolling_trend(ctx: Ctx):
    rows_all: dict[int, dict] = {}
    for season in ("summer", "winter"):
        if ctx.season and ctx.season != season:
            continue
        w, par = Ctx({**ctx.p, "season": season}).where()
        e = df(f"SELECT year, female_share FROM gold_edition_performance WHERE 1=1 {w} ORDER BY year", **par).dropna()
        for i in range(4, len(e)):
            win = e.iloc[i - 4:i + 1]
            slope = np.polyfit(win.year, win.female_share * 100, 1)[0] * 4  # percentage points per 4-year cycle
            rows_all.setdefault(int(e.year.iloc[i]), {"year": int(e.year.iloc[i])})[season.capitalize()] = round(float(slope), 2)
    rows = need_rows([rows_all[k] for k in sorted(rows_all)], "editions (needs 5 editions per window)")
    keys = [k for k in ("Summer", "Winter") if any(k in r for r in rows)]
    return payload("ts_rolling_trend", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys, colors=SEASON_COLORS), "variant": "line", "dot": True,
                   "xLabel": "End year of 5-edition window", "yLabel": "Change in female share (percentage points per 4 years)", "refs": [{"y": 0, "label": "no change"}]},
                   axes={"x": "Window end year", "y": "pp per 4 years"}, ctx=ctx,
                   interpretation="Each point is the least-squares slope of female share over the latest 5 editions of that season, expressed as percentage points per 4-year cycle. "
                                  "Positive values mean women's share was rising.")


@chart("ts_step_events", S, "overview", "Events on the programme (step chart)", "xy", "Gold edition performance", "gold_edition_performance",
       "Show programme changes as discrete jumps between editions", ("season", "year_range"), ("line", "bar"))
def step_events(ctx: Ctx):
    e = _editions(ctx)
    e["Season"] = e.season.str.capitalize()
    rows, keys = wide(e, "year", "Season", "events")
    return payload("ts_step_events", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys, colors=SEASON_COLORS), "variant": "step", "dot": True,
                   "xLabel": "Games year", "yLabel": "Events contested"}, axes={"x": "Games year", "y": "Events"}, ctx=ctx,
                   interpretation="The programme only changes between Games, so a step chart is the honest shape: the value is constant within an edition.")


@chart("ts_slope_rank", S, "overview", "Slope chart: medals, first vs last Games in range", "slope", "Gold country medals", "gold_country_medals",
       "Show who gained or lost medal share between two editions", ("season", "year_range", "top"), ("table",))
def slope_rank(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = c.where()
    g = df(f"SELECT DISTINCT games_id, year FROM gold_country_medals WHERE 1=1 {w} ORDER BY year", **par)
    if len(g) < 2:
        raise Unavailable("need at least two Games in the selected range")
    a, b = g.iloc[0], g.iloc[-1]
    top = ctx.top or 12
    d = df("SELECT g.games_id, g.noc_code, g.country_name, g.total, g.official_rank FROM gold_country_medals g WHERE g.games_id IN (:a,:b)", a=a.games_id, b=b.games_id)
    best = d[d.games_id == b.games_id].sort_values("total", ascending=False).head(top).noc_code.tolist()
    d = d[d.noc_code.isin(best)]
    pv = d.pivot_table(index=["noc_code", "country_name"], columns="games_id", values="total", aggfunc="sum").fillna(0).reset_index()
    rows = [{"name": f"{r.country_name} ({r.noc_code})", "noc": r.noc_code, "from": float(r[a.games_id]), "to": float(r[b.games_id])} for _, r in pv.iterrows()]
    return payload("ts_slope_rank", "slope", {"left": a.games_id.replace("_", " "), "right": b.games_id.replace("_", " "), "rows": rows, "yLabel": "Medals won in that Games"},
                   axes={"y": "Medals"}, ctx=ctx, table=table_from(rows), drill={"type": "country", "key": "noc"},
                   interpretation=f"The {top} nations with most medals in {b.games_id.replace('_', ' ')}, compared with the same nations in {a.games_id.replace('_', ' ')}. "
                                  "Zero means the NOC won no medals (or did not exist) in the earlier Games; dissolved delegations such as the USSR appear only on the left.")


@chart("ts_bump_rank", S, "overview", "Bump chart: official medal-table rank", "xy", "Gold country medals", "gold_country_medals",
       "Show changing country rankings across Games", ("season", "year_range", "top", "nocs"), ("line",))
def bump_rank(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    nocs = top_nocs(c, ctx.top or 10)
    w, par = c.where()
    d = df(f"SELECT year, noc_code, official_rank FROM gold_country_medals WHERE noc_code IN ({','.join(f':n{i}' for i in range(len(nocs)))}) AND official_rank IS NOT NULL {w}",
           **par, **{f"n{i}": n for i, n in enumerate(nocs)})
    need_rows(d, "ranks")
    rows, keys = wide(d, "year", "noc_code", "official_rank")
    names = noc_names()
    maxrank = int(d.official_rank.max())
    return payload("ts_bump_rank", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys, names={k: names.get(k, {}).get("name", k) for k in keys}), "variant": "line", "dot": True,
                   "invertY": True, "yDomain": [1, maxrank], "curve": "linear", "xLabel": "Games year", "yLabel": "Rank (1 = best)", "endLabels": True}, axes={"x": "Games year", "y": "Rank"}, ctx=ctx,
                   drill={"type": "country", "key": "series"},
                   interpretation="Lower is better (rank 1 at the top). Rank follows the official order: gold, then silver, then bronze; tied NOCs share a rank. A gap means the NOC did not appear in that Games.")


@chart("ts_calendar_activity", S, "editions", "Competition-day activity calendar", "calendar", "Matches with dates", "matches",
       "Show on which days of each Games matches were played", ("season", "year_range"), ())
def calendar_activity(ctx: Ctx):
    w, par = ctx.where("g")
    d = df(f"SELECT m.games_id, g.year, g.season, g.opening_date, m.match_date FROM olympedia_matches m JOIN games g USING(games_id) WHERE m.match_date IS NOT NULL AND g.year<=2026 {w}", **par)
    need_rows(d, "dated matches")
    d["md"] = pd.to_datetime(d.match_date.str.extract(r"(\d{1,2} [A-Za-z]+ \d{4})")[0], format="%d %B %Y", errors="coerce")
    d["od"] = pd.to_datetime(d.opening_date, errors="coerce")
    d["od"] = d.od.fillna(d.groupby("games_id").md.transform("min"))
    d["day"] = (d.md - d.od).dt.days
    d = d[(d.day >= -1) & (d.day <= 30)]
    cnt = d.groupby(["games_id", "year", "season", "day"]).size().reset_index(name="matches")
    need_rows(cnt, "dated matches")
    order = cnt[["games_id", "year", "season"]].drop_duplicates().sort_values(["year", "season"]).games_id.tolist()
    cap = float(np.percentile(cnt.matches, 97))
    rows = [{"r": g.replace("_", " ").title(), "c": int(day), "v": int(m), "label": f"{g.replace('_', ' ')}, day {int(day)}: {m:,} matches"} for g, day, m in zip(cnt.games_id, cnt.day, cnt.matches)]
    return payload("ts_calendar_activity", "calendar", {"rows": rows, "rowOrder": [g.replace("_", " ").title() for g in order], "colOrder": list(range(0, 31)), "scale": "seq", "clipMax": cap,
                   "vLabel": "Matches played that day", "colLabel": "Day of the Games (0 = opening date)", "format": "int"}, axes={"x": "Day of the Games", "y": "Games"}, ctx=ctx,
                   interpretation="Each cell is one calendar day of a Games, coloured by the number of recorded matches (Olympedia fixtures; the colour scale is capped at the 97th percentile so a few very large days, such as the modern pentathlon fencing ranking round, do not hide the rest). "
                                  "Only sports whose individual fixtures were collected (team sports, combat sports, racket sports, fencing, archery) are counted, so this shows activity of match-based sports, not the whole programme.", drill={"type": "games", "key": "games_id"})
