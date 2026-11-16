"""Section 4 - sports and events charts."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .core import MEDAL_COLORS, Ctx, Unavailable, analytics, box_stats, chart, df, need_rows, payload, series_defs, table_from, wide

S = 4
GENDER_COLORS = {"Men": "#0085C7", "Women": "#DF0024"}
DEFAULT_EVENT = ("Athletics", "100 metres, Men")


def parse_value(text) -> float | None:
    """First numeric token of a recorded result: '10.2 (1)' -> 10.2, '1:47.5' -> 107.5 s, '2,528' -> 2528, '10.0w (2.8 m/s)' -> 10.0."""
    if text is None:
        return None
    tok = str(text).strip().split(" ")[0]
    tok = re.sub(r"[A-Za-z*]+$", "", tok)
    if re.match(r"^\d{1,3}(,\d{3})+(\.\d+)?$", tok):
        tok = tok.replace(",", "")
    m = re.match(r"^(\d+(?::\d+){0,2}(?:[.,]\d+)?)$", tok)
    if not m:
        return None
    t = m.group(1).replace(",", ".")
    if ":" in t:
        parts = [float(x) for x in t.split(":")]
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec
    return float(t)


def unit_for(event: str, header: str | None = None) -> tuple[str, bool]:
    """(axis label, lower_is_better) from the event name / result header - never guessed silently: unknown -> as recorded."""
    e = (event or "").lower()
    h = (header or "").lower()
    if re.search(r"decathlon|heptathlon|pentathlon|gymnastic|all-around|vault|pommel|rings|parallel bars|horizontal bar|uneven bars|balance beam|floor exercise|trampoline|diving|platform|springboard|figure skating|ski jumping|aerials|moguls|halfpipe|slopestyle|big air|artistic swimming|synchron|rhythmic|dressage|points race|omnium", e) and not re.search(r"\d\s*(m|metres|kilometres|km)", e):
        return "Points", False
    if h.startswith("time") or re.search(r"\d\s*(m|metres|kilometres|km)\b|relay|marathon|hurdles|steeplechase|freestyle|backstroke|breaststroke|butterfly|medley|sprint|keirin|time trial|pursuit|skeleton|luge|bobsleigh|slalom|giant|downhill|super-g|combined|cross-country|biathlon|rowing|eights|coxed|coxless|sculls|kayak|canadian|canoeing|speed skating|short track|marathon|walk|triathlon|bobsled|two-man|four-man|fours?|pairs?", e) and not re.search(r"jump|throw|put|vault|discus|hammer|javelin|shot|weight", e):
        return "Time (seconds)", True
    if re.search(r"jump|throw|put|vault|discus|hammer|javelin|shot", e):
        return "Distance or height (metres)", False
    if "kg" in h or "weight" in h or "lift" in e or "snatch" in e or "clean" in e:
        return "Weight lifted (kg)", False
    if "point" in h or "round" in e or "archery" in e or "shooting" in e or "pistol" in e or "rifle" in e or "athlon" in e:
        return "Points", False
    return "Result as recorded (unit varies by event)", False


def _sp_where(ctx: Ctx, alias: str = "g"):
    w, par = ctx.where(alias)
    if ctx.sport:
        w += f" AND {alias}.sport_name=:_sport"; par["_sport"] = ctx.sport
    return w, par


@chart("s_participation_bar", S, "sports", "Sports by number of participants", "xy", "Gold sport performance", "gold_sport_performance",
       "Show which sports attract the most athletes", ("season", "year_range", "top"), ("treemap", "donut"))
def participation_bar(ctx: Ctx):
    w, par = ctx.where("g")
    d = df(f"SELECT g.sport_name, SUM(g.athletes) athletes, COUNT(DISTINCT g.games_id) games FROM gold_sport_performance g WHERE 1=1 {w} GROUP BY 1 ORDER BY 2 DESC LIMIT {int(ctx.top or 20)}", **par)
    need_rows(d, "sports")
    rows = [{"name": r.sport_name, "Athlete entries": int(r.athletes), "games": int(r.games)} for r in d.itertuples()]
    return payload("s_participation_bar", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": "Athlete entries", "color": "#0085C7"}], "variant": "bar", "horizontal": True,
                   "yLabel": "Athlete entries (sum over Games)", "pickKey": "name"}, axes={"x": "Athlete entries", "y": "Sport"}, ctx=ctx, drill={"type": "sport", "key": "name"},
                   interpretation="An athlete competing in two sports at one Games counts once in each sport, and an athlete at several Games counts once per Games.")


@chart("s_evolution_timeline", S, "sports", "Sports evolution timeline", "timeline", "Gold sport performance", "gold_sport_performance",
       "Show when each sport has been on the programme", ("season",), ("table",))
def evolution_timeline(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = c.where("g")
    d = df(f"SELECT g.sport_name, g.year, g.events FROM gold_sport_performance g WHERE g.athletes>0 {w} ORDER BY g.year", **par)
    need_rows(d, "sports")
    first = d.groupby("sport_name").year.min().sort_values()
    rows = [{"lane": r.sport_name, "start": int(r.year), "end": int(r.year) + 2, "label": f"{r.sport_name} {int(r.year)}: {int(r.events)} events", "color": "#0085C7" if c.season == "winter" else "#F4A300", "group": c.season or "summer"}
            for r in d.itertuples()]
    return payload("s_evolution_timeline", "timeline", {"rows": rows, "laneOrder": first.index.tolist(), "xLabel": "Games year", "unit": "year", "legend": []}, axes={"x": "Games year", "y": "Sport"}, ctx=ctx,
                   drill={"type": "sport", "key": "lane"}, table=table_from([{"sport": r["lane"], "year": r["start"], "events": r["label"].split(": ")[1]} for r in rows]),
                   interpretation=f"One block per Games in which the sport had athletes ({(c.season or 'summer').capitalize()} Games since {int(d.year.min())}). Sports are ordered by first appearance, so gaps show withdrawn-and-returned sports and the lower rows show newcomers.")


@chart("s_event_progression", S, "sports", "Event count progression by sport", "xy", "Gold sport performance", "gold_sport_performance",
       "Show which sports drove the growth of the programme", ("season", "year_range"), ("area", "percent", "bar"))
def event_progression(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = c.where("g")
    d = df(f"SELECT g.year, g.sport_name, g.events FROM gold_sport_performance g WHERE 1=1 {w}", **par)
    need_rows(d, "events")
    top = d.groupby("sport_name").events.sum().sort_values(ascending=False).head(8).index
    d["s"] = np.where(d.sport_name.isin(top), d.sport_name, "All other sports")
    rows, keys = wide(d, "year", "s", "events", fill=0)
    keys = [k for k in keys if k != "All other sports"] + (["All other sports"] if "All other sports" in keys else [])
    return payload("s_event_progression", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys), "variant": "stacked", "xLabel": "Games year", "yLabel": "Events contested"},
                   axes={"x": "Games year", "y": "Events"}, ctx=ctx, drill={"type": "sport", "key": "series"},
                   interpretation=f"Stacked events per Games ({(c.season or 'summer').capitalize()}) for the 8 sports with most event-editions, all other sports combined. Total height is the whole programme.")


@chart("s_popularity_area", S, "sports", "Sports popularity over time", "xy", "Gold sport performance", "gold_sport_performance",
       "Show the changing mix of athletes across sports", ("season", "year_range"), ("percent", "bar", "line"))
def popularity_area(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = c.where("g")
    d = df(f"SELECT g.year, g.sport_name, g.athletes FROM gold_sport_performance g WHERE 1=1 {w}", **par)
    need_rows(d, "athletes")
    top = d.groupby("sport_name").athletes.sum().sort_values(ascending=False).head(9).index
    d["s"] = np.where(d.sport_name.isin(top), d.sport_name, "All other sports")
    rows, keys = wide(d, "year", "s", "athletes", fill=0)
    keys = [k for k in keys if k != "All other sports"] + (["All other sports"] if "All other sports" in keys else [])
    return payload("s_popularity_area", "xy", {"x": "year", "xType": "number", "rows": rows, "series": series_defs(keys), "variant": "stacked", "xLabel": "Games year", "yLabel": "Athlete entries"},
                   axes={"x": "Games year", "y": "Athlete entries"}, ctx=ctx, drill={"type": "sport", "key": "series"},
                   interpretation=f"Athlete entries per sport for the 9 largest sports plus all others ({(c.season or 'summer').capitalize()}). Switch to the percent view to see share of all entries.")


@chart("s_medal_heatmap", S, "sports", "Medal awards by sport and Games", "heatmap", "Gold sport performance", "gold_sport_performance",
       "Show where in the programme medals are decided", ("season", "year_range", "top"), ())
def medal_heatmap(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = c.where("g")
    d = df(f"SELECT g.year, g.sport_name, g.medal_awards FROM gold_sport_performance g WHERE g.medal_awards>0 {w}", **par)
    need_rows(d, "medal awards")
    top = d.groupby("sport_name").medal_awards.sum().sort_values(ascending=False).head(ctx.top or 25).index.tolist()
    d = d[d.sport_name.isin(top)]
    rows = [{"r": r.sport_name, "c": str(int(r.year)), "v": int(r.medal_awards), "label": f"{r.sport_name} {int(r.year)}: {int(r.medal_awards)} medal awards"} for r in d.itertuples()]
    return payload("s_medal_heatmap", "heatmap", {"rows": rows, "rowOrder": top, "colOrder": [str(y) for y in sorted(d.year.unique())], "scale": "seq", "vLabel": "Medal awards", "format": "int"},
                   axes={"x": "Games year", "y": "Sport"}, ctx=ctx, drill={"type": "sport", "key": "r"},
                   interpretation="Medal awards are individual medals handed out (a team medal counts for each team member), so team sports show larger numbers than their event count suggests.")


@chart("s_country_sport_heatmap", S, "sports", "Country versus sport medal heatmap", "heatmap", "Medal table by sport", "medal_table_by_sport",
       "Reveal which nations dominate which sports", ("season", "year_range", "top"), ())
def country_sport_heatmap(ctx: Ctx):
    w, par = ctx.where("g")
    d = df(f"""SELECT m.noc_code, s.sport_name, SUM(m.total) medals FROM medal_table_by_sport m JOIN games g USING(games_id) JOIN sports s USING(sport_id) WHERE m.total>0 {w} GROUP BY 1,2""", **par)
    need_rows(d, "medals")
    nocs = d.groupby("noc_code").medals.sum().sort_values(ascending=False).head(ctx.top or 15).index.tolist()
    spo = d[d.noc_code.isin(nocs)].groupby("sport_name").medals.sum().sort_values(ascending=False).head(22).index.tolist()
    d = d[d.noc_code.isin(nocs) & d.sport_name.isin(spo)]
    rows = [{"r": r.noc_code, "c": r.sport_name, "v": int(r.medals), "label": f"{r.noc_code} in {r.sport_name}: {int(r.medals)} medals"} for r in d.itertuples()]
    return payload("s_country_sport_heatmap", "heatmap", {"rows": rows, "rowOrder": nocs, "colOrder": spo, "scale": "seq", "vLabel": "Medals", "format": "int", "rotateCols": True}, axes={"x": "Sport", "y": "NOC"}, ctx=ctx,
                   drill={"type": "country", "key": "r"}, interpretation="Medals in the official sport-level medal tables (a team medal counts once). Only the leading nations and the sports in which they win most are shown; blank cells have no medals.")


@chart("s_specialization_bubble", S, "sports", "Sport specialization of nations", "scatter", "ML sport specialization", "analytics_results(ml/sport_specialization)",
       "Show whether nations win medals in many sports or concentrate in a few", (), ("table",))
def specialization_bubble(ctx: Ctx):
    p = analytics("ml", "sport_specialization")
    d = pd.DataFrame(p["countries"])
    d = d[d.total_medals >= 3]
    need_rows(d, "nations")
    rows = [{"name": r.historical_name, "noc": r.noc_code, "x": float(r.n_medal_sports), "y": float(r.sport_hhi), "z": int(r.total_medals), "group": r.profile, "dominant": f"{r.dominant_sport} ({100 * r.dominant_sport_share:.0f}%)"}
            for r in d.itertuples()]
    return payload("s_specialization_bubble", "scatter", {"rows": rows, "xLabel": "Number of sports with a medal", "yLabel": "Concentration index (HHI of medal shares; 1 = one sport)", "sizeLabel": "Total medals", "groupLabel": "Profile",
                   "extra": ["dominant"], "logX": True}, axes={"x": "Medal sports (log)", "y": "HHI"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation="HHI is the sum of squared shares of a nation's medals across sports: 1 means all medals in one sport, values near 0 mean broad success. Large bubbles with low HHI are all-round powers; "
                                  "small nations with HHI = 1 owe all medals to one sport. Nations with fewer than 3 medals are omitted.")


@chart("s_result_hist", S, "sports", "Distribution of results in an event", "xy", "Olympedia event rows", "olympedia_event_rows",
       "Show the spread of performances in one event across all Games", ("sport", "event"), ("box",))
def result_hist(ctx: Ctx):
    sport, event = ctx.sport or DEFAULT_EVENT[0], ctx.event or DEFAULT_EVENT[1]
    d = df("SELECT games_id, result_text, result_header FROM olympedia_event_rows WHERE is_main=1 AND sport_name=:s AND event_name=:e", s=sport, e=event)
    need_rows(d, f"results for {sport} / {event}")
    d["v"] = d.result_text.map(parse_value)
    d = d.dropna(subset=["v"])
    unit, lower = unit_for(event, d.result_header.mode().iat[0] if d.result_header.notna().any() else None)
    if len(d) < 15:
        raise Unavailable(f"fewer than 15 numeric results recorded for {sport} / {event}")
    lo, hi = d.v.quantile(.005), d.v.quantile(.995)
    v = d.v[(d.v >= lo) & (d.v <= hi)]
    counts, edges = np.histogram(v, bins=30)
    rows = [{"bin": round(float((edges[i] + edges[i + 1]) / 2), 3), "Results": int(counts[i]), "from": round(float(edges[i]), 3), "to": round(float(edges[i + 1]), 3)} for i in range(len(counts))]
    return payload("s_result_hist", "xy", {"x": "bin", "xType": "number", "rows": rows, "series": [{"key": "Results", "color": "#0085C7"}], "variant": "bar", "barGap": 0, "xLabel": unit, "yLabel": "Number of results",
                   "refs": [{"x": round(float(v.median()), 3), "label": f"median {v.median():.2f}"}]}, axes={"x": unit, "y": "Results"}, ctx=ctx,
                   interpretation=f"{len(d):,} recorded results for {sport} - {event} across all Games (the extreme 1% are trimmed from the view; {len(d) - len(v)} points). "
                                  f"{'Lower is better.' if lower else 'Higher is better.'} Only results with a recorded numeric mark in the event's main results table are included (mostly finals), so athletes eliminated in heats are largely absent.",
                   notes=[f"Event: {sport} / {event}. Change it with the sport and event filters."])


@chart("s_result_decades", S, "sports", "Results of an event by decade", "box", "Olympedia event rows", "olympedia_event_rows",
       "Show how performance in one event changed decade by decade", ("sport", "event"), ("violin",))
def result_decades(ctx: Ctx):
    sport, event = ctx.sport or DEFAULT_EVENT[0], ctx.event or DEFAULT_EVENT[1]
    d = df("SELECT games_id, result_text, result_header FROM olympedia_event_rows WHERE is_main=1 AND sport_name=:s AND event_name=:e", s=sport, e=event)
    need_rows(d, f"results for {sport} / {event}")
    d["v"] = d.result_text.map(parse_value)
    d["decade"] = (d.games_id.str[:4].astype(int) // 10 * 10).astype(str) + "s"
    d = d.dropna(subset=["v"])
    unit, lower = unit_for(event, d.result_header.mode().iat[0] if d.result_header.notna().any() else None)
    groups = [{"name": dec, **box_stats(g.v.values)} for dec, g in d.groupby("decade") if len(g) >= 8]
    need_rows(groups, "decades with at least 8 results")
    return payload("s_result_decades", "box", {"groups": groups, "yLabel": unit, "orientation": "v"}, axes={"x": "Decade", "y": unit}, ctx=ctx,
                   table=table_from([{k: v for k, v in g.items() if k != "outliers"} for g in groups]),
                   interpretation=f"{sport} - {event}: results per decade (recorded marks from the main results table, mostly finals). {'Lower is better.' if lower else 'Higher is better.'} Rule changes, equipment, timing technology and a different mix of rounds all move these distributions, not only athletic progress.")


def _records(event: str, season: str | None = None) -> pd.DataFrame:
    """Record rows of one event. The same event name exists in both seasons (e.g. 1,500 metres: athletics vs speed skating), so one season is chosen."""
    g = df("SELECT games_id, noc_code, record_level, record_type, record_value, description FROM gold_records")
    g["event"] = g.description.str.split(" | ", regex=False).str[0]
    g = g[g.event == event].copy()
    g["season"] = g.games_id.str.split("_").str[1]
    if season is None:
        season = g.season.value_counts().index[0] if len(g) else None
    g = g[g.season == season].copy()
    g["year"] = g.games_id.str[:4].astype(int)
    g["v"] = g.record_value.map(parse_value)
    return g.dropna(subset=["v"])


def _default_record_event() -> str:
    g = df("SELECT description, record_level FROM gold_records")
    g["event"] = g.description.str.split(" | ", regex=False).str[0]
    c = g.groupby(["event", "record_level"]).size().unstack(fill_value=0)
    c = c[(c.get("world", 0) >= 3) & (c.get("olympic", 0) >= 3)]
    if "100 metres, Men" in c.index:
        return "100 metres, Men"
    return c.sort_values("world", ascending=False).index[0]


@chart("s_record_progression", S, "records", "Olympic record progression", "xy", "Gold records", "gold_records",
       "Show how the Olympic record in one event improved over the Games", ("event", "season"), ("line", "step"))
def record_progression(ctx: Ctx):
    event = ctx.event or _default_record_event()
    g = _records(event, ctx.season)
    need_rows(g, f"records for {event}")
    unit, lower = unit_for(event)
    o = g[g.record_level == "olympic"]
    need_rows(o, "Olympic records")
    best = o.groupby("year").v.agg("min" if lower else "max").reset_index()
    best["running"] = best.v.cummin() if lower else best.v.cummax()
    rows = [{"year": int(r.year), "Best mark at that Games": round(float(r.v), 3), "Olympic record at that time": round(float(r.running), 3)} for r in best.itertuples()]
    return payload("s_record_progression", "xy", {"x": "year", "xType": "number", "rows": rows, "series": [{"key": "Best mark at that Games", "color": "#9AA3AF"}, {"key": "Olympic record at that time", "color": "#DF0024"}],
                   "variant": "step", "dot": True, "xLabel": "Games year", "yLabel": unit, "yAuto": True}, axes={"x": "Games year", "y": unit}, ctx=ctx,
                   interpretation=f"{event}: best mark recorded at each Games where an Olympic record or best performance was noted, and the running Olympic record. {'Lower is better.' if lower else 'Higher is better.'} "
                                  "Marks with wind assistance keep their recorded value; mixed conditions are not corrected.",
                   notes=[f"Event shown: {event} ({g.season.iloc[0]} Games). Pick another with the event filter (events with at least 3 records); an event name that exists in both seasons shows the season with more records unless the season filter is set."])


@chart("s_or_vs_wr", S, "records", "Olympic record versus world record", "xy", "Gold records", "gold_records",
       "Compare Olympic records with world records in the same event", ("event", "season"), ("line",))
def or_vs_wr(ctx: Ctx):
    event = ctx.event or _default_record_event()
    g = _records(event, ctx.season)
    need_rows(g, f"records for {event}")
    unit, lower = unit_for(event)
    o = g[g.record_level == "olympic"].groupby("year").v.agg("min" if lower else "max")
    w = g[g.record_level == "world"].groupby("year").v.agg("min" if lower else "max")
    if w.empty or o.empty:
        raise Unavailable(f"{event} has no records at both levels")
    years = sorted(set(o.index) | set(w.index))
    rows = [{"year": int(y), "Olympic best / record": None if y not in o.index else round(float(o[y]), 3), "World record set at these Games": None if y not in w.index else round(float(w[y]), 3)} for y in years]
    return payload("s_or_vs_wr", "xy", {"x": "year", "xType": "number", "rows": rows, "series": [{"key": "Olympic best / record", "color": "#D4AF37"}, {"key": "World record set at these Games", "color": "#DF0024"}],
                   "variant": "line", "dot": True, "xLabel": "Games year", "yLabel": unit, "yAuto": True}, axes={"x": "Games year", "y": unit}, ctx=ctx,
                   interpretation=f"{event}: only world records set (or equalled) during an Olympic Games are in the data, so the red points are sparse by construction. {'Lower is better.' if lower else 'Higher is better.'} "
                                  "Both series are in the same unit.", notes=[f"Event shown: {event} ({g.season.iloc[0]} Games)."])


@chart("s_gender_by_sport", S, "sports", "Gender participation by sport", "xy", "Gold gender participation", "gold_gender_participation",
       "Show how balanced each sport is between men and women", ("season", "year_range", "top"), ("percent", "stacked"))
def gender_by_sport(ctx: Ctx):
    w, par = ctx.where("g")
    d = df(f"SELECT g.sport_name, g.gender, SUM(g.athletes) athletes FROM gold_gender_participation g WHERE g.gender IN ('M','F') {w} GROUP BY 1,2", **par)
    need_rows(d, "athletes")
    pv = d.pivot_table(index="sport_name", columns="gender", values="athletes", fill_value=0)
    pv["total"] = pv.sum(axis=1)
    pv = pv.sort_values("total", ascending=False).head(ctx.top or 18)
    rows = [{"name": i, "Men": int(r.get("M", 0)), "Women": int(r.get("F", 0)), "female_share": round(float(r.get("F", 0)) / r.total, 3) if r.total else None} for i, r in pv.iterrows()]
    return payload("s_gender_by_sport", "xy", {"x": "name", "xType": "category", "rows": rows, "series": series_defs(["Men", "Women"], colors=GENDER_COLORS), "variant": "grouped", "horizontal": True,
                   "yLabel": "Athlete entries", "pickKey": "name"}, axes={"x": "Athlete entries", "y": "Sport"}, ctx=ctx, drill={"type": "sport", "key": "name"},
                   interpretation="The most-attended sports in the window; female share is in the data table. Sports with men-only or women-only programmes (e.g. rhythmic gymnastics, Nordic combined) show one-sided bars by design of the programme.")
