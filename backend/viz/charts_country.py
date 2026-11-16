"""Section 2 - country and medal charts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import (MEDAL_COLORS, Ctx, Unavailable, chart, df, gini, need_rows, noc_names, payload, series_defs, table_from, top_nocs, wide)

S = 2
GSB = {"Gold": MEDAL_COLORS["Gold"], "Silver": MEDAL_COLORS["Silver"], "Bronze": MEDAL_COLORS["Bronze"]}


def window_medals(ctx: Ctx) -> pd.DataFrame:
    """Per-NOC medal totals inside the active season / year window (official medal tables)."""
    w, par = ctx.where("g")
    d = df(f"""SELECT g.noc_code, COALESCE(h.historical_name, MAX(g.country_name)) name, h.continent, h.iso_alpha3 iso3,
                      SUM(g.gold) Gold, SUM(g.silver) Silver, SUM(g.bronze) Bronze, SUM(g.total) Total, COUNT(*) editions, SUM(g.athletes) athlete_entries
               FROM gold_country_medals g LEFT JOIN historical_nocs h USING(noc_code) WHERE 1=1 {w} GROUP BY g.noc_code ORDER BY Total DESC, Gold DESC""", **par)
    return need_rows(d, "medals")


def _top(ctx: Ctx, default: int = 15) -> pd.DataFrame:
    d = window_medals(ctx)
    if ctx.nocs:
        return d[d.noc_code.isin(ctx.nocs)]
    return d.head(ctx.top or default)


def _window_label(ctx: Ctx) -> str:
    bits = [ctx.season.capitalize() if ctx.season else "Summer + Winter", f"{ctx.year_from or 1960}-{ctx.year_to or 2026}"]
    return ", ".join(bits)


@chart("c_rank_hbar", S, "medals", "Medal ranking (horizontal bars)", "xy", "Gold country medals", "gold_country_medals",
       "Rank nations by total medals in the selected window", ("season", "year_range", "top", "nocs"), ("donut", "treemap"))
def rank_hbar(ctx: Ctx):
    d = _top(ctx, 15)
    rows = [{"name": r.name, "noc": r.noc_code, "Total medals": int(r.Total)} for r in d.itertuples()]
    return payload("c_rank_hbar", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": "Total medals", "color": "#0085C7"}], "variant": "bar", "horizontal": True,
                   "yLabel": "Total medals", "xLabel": None, "pickKey": "noc"}, axes={"x": "Medals", "y": "Nation"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation=f"{d.iloc[0]['name']} leads with {int(d.iloc[0].Total):,} medals ({_window_label(ctx)}). Counts follow the official medal tables, so a team medal counts once for the NOC. "
                                  "Dissolved delegations (USSR, East Germany, ...) are ranked under their own NOC code.")


@chart("c_grouped_gsb", S, "medals", "Gold, silver and bronze by nation (grouped)", "xy", "Gold country medals", "gold_country_medals",
       "Compare medal composition of leading nations", ("season", "year_range", "top", "nocs"), ("stacked", "rank_hbar"))
def grouped_gsb(ctx: Ctx):
    d = _top(ctx, 10)
    rows = [{"name": r.noc_code, "full": r.name, "Gold": int(r.Gold), "Silver": int(r.Silver), "Bronze": int(r.Bronze)} for r in d.itertuples()]
    return payload("c_grouped_gsb", "xy", {"x": "name", "xType": "category", "rows": rows, "series": series_defs(["Gold", "Silver", "Bronze"], colors=GSB), "variant": "grouped",
                   "yLabel": "Medals", "xLabel": "NOC", "pickKey": "name"}, axes={"x": "NOC", "y": "Medals"}, ctx=ctx, drill={"type": "country", "key": "name"},
                   interpretation="Bars use the conventional medal colours. A nation's gold share (gold / total) shows whether its medals skew towards titles or towards podium depth.")


@chart("c_stacked_gsb", S, "medals", "Medal composition (stacked)", "xy", "Gold country medals", "gold_country_medals",
       "Show total medals and their composition in one bar", ("season", "year_range", "top", "nocs"), ("percent", "grouped"))
def stacked_gsb(ctx: Ctx):
    d = _top(ctx, 12)
    rows = [{"name": r.noc_code, "Gold": int(r.Gold), "Silver": int(r.Silver), "Bronze": int(r.Bronze)} for r in d.itertuples()]
    return payload("c_stacked_gsb", "xy", {"x": "name", "xType": "category", "rows": rows, "series": series_defs(["Gold", "Silver", "Bronze"], colors=GSB), "variant": "stacked",
                   "yLabel": "Medals", "xLabel": "NOC", "pickKey": "name"}, axes={"x": "NOC", "y": "Medals"}, ctx=ctx, drill={"type": "country", "key": "name"},
                   interpretation="Total bar height is the medal count; the colour split is the composition. Use the percent view to compare composition independent of size.")


@chart("c_progression", S, "medals", "Cumulative medal progression", "xy", "Gold country medals", "gold_country_medals",
       "Show how leading nations accumulated medals over the Games", ("season", "year_range", "nocs", "top"), ("line", "area"))
def progression(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    nocs = top_nocs(c, ctx.top or 6)
    w, par = c.where()
    ph = ",".join(f":n{i}" for i in range(len(nocs)))
    d = df(f"SELECT year, noc_code, total FROM gold_country_medals WHERE noc_code IN ({ph}) {w}", **par, **{f"n{i}": n for i, n in enumerate(nocs)})
    need_rows(d, "medals")
    years = sorted(df(f"SELECT DISTINCT year FROM gold_country_medals WHERE 1=1 {w}", **par).year.tolist())
    pv = d.pivot_table(index="year", columns="noc_code", values="total", aggfunc="sum").reindex(years).fillna(0).cumsum().reset_index()
    names = noc_names()
    return payload("c_progression", "xy", {"x": "year", "xType": "number", "rows": pv.to_dict("records"), "series": series_defs([c for c in pv.columns if c != "year"], names={k: names.get(k, {}).get("name", k) for k in nocs}),
                   "variant": "line", "xLabel": "Games year", "yLabel": f"Cumulative medals ({(c.season or 'summer').capitalize()} Games)", "endLabels": False}, axes={"x": "Games year", "y": "Cumulative medals"}, ctx=ctx,
                   drill={"type": "country", "key": "series"}, interpretation="Each line adds a nation's medals Games by Games within one season (default Summer). Flat stretches mean no medals or absence from those Games.")


@chart("c_share_donut", S, "medals", "Medal share by nation (donut)", "donut", "Gold country medals", "gold_country_medals",
       "Show how concentrated medals are among the leaders", ("season", "year_range", "top"), ("bar", "treemap"))
def share_donut(ctx: Ctx):
    d = window_medals(ctx)
    n = min(ctx.top or 8, 10)
    head, tail = d.head(n), d.iloc[n:]
    rows = [{"name": r.name, "noc": r.noc_code, "value": int(r.Total)} for r in head.itertuples()]
    if len(tail):
        rows.append({"name": f"Other ({len(tail)} NOCs)", "noc": None, "value": int(tail.Total.sum())})
    tot = d.Total.sum()
    return payload("c_share_donut", "donut", {"rows": rows, "valueLabel": "medals", "total": int(tot)}, axes={}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation=f"The top {n} nations hold {100 * head.Total.sum() / tot:.1f}% of {int(tot):,} medals in this window. To stay readable the chart never shows more than 11 slices; the remainder is grouped as Other.")


@chart("c_treemap", S, "medals", "Medal distribution treemap (continent, nation)", "treemap", "Gold country medals x historical NOCs", "gold_country_medals",
       "Show the hierarchy of medals from continent to nation", ("season", "year_range"), ("donut", "bar"))
def treemap(ctx: Ctx):
    d = window_medals(ctx)
    d["continent"] = d.continent.fillna("Neutral / unassigned")
    d = d[d.Total > 0]
    keep = d.head(60)
    rest = d.iloc[60:]
    rows = [{"name": r.name, "noc": r.noc_code, "group": r.continent, "size": int(r.Total)} for r in keep.itertuples()]
    if len(rest):
        rows.append({"name": f"{len(rest)} smaller NOCs", "noc": None, "group": "Other", "size": int(rest.Total.sum())})
    return payload("c_treemap", "treemap", {"rows": rows, "sizeLabel": "medals"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation="Area is proportional to medals; colour is the continent. The 60 largest NOCs are drawn individually and all smaller NOCs are merged into one block so every medal is counted.")


RADAR_AXES = [("medals_per_appearance", "Medals per Games"), ("gold_ratio", "Gold share"), ("n_sports", "Medal sports"), ("athletes_per_games", "Delegation size"), ("appearances", "Games attended"), ("winter_share", "Winter share")]


@chart("c_radar", S, "countries", "Country comparison radar", "radar", "ML clustering features / participation history", "gold_country_participation_history",
       "Compare the Olympic profile of several nations on common, normalised axes", ("nocs",), ("table",))
def radar(ctx: Ctx):
    nocs = ctx.nocs or top_nocs(Ctx({}), 4)
    ph = ",".join(f":n{i}" for i in range(len(nocs)))
    par = {f"n{i}": n for i, n in enumerate(nocs)}
    h = df(f"SELECT noc_code, historical_name, appearances, athletes, gold, silver, bronze, total_medals, summer_appearances, winter_appearances FROM gold_country_participation_history WHERE noc_code IN ({ph})", **par)
    sp = df(f"SELECT noc_code, COUNT(DISTINCT sport_name) n_sports FROM silver_medal_awards WHERE noc_code IN ({ph}) GROUP BY 1", **par)
    wm = df(f"SELECT a.noc_code, SUM(CASE WHEN g.season='winter' THEN 1 ELSE 0 END)*1.0/COUNT(*) winter_share FROM silver_medal_awards a JOIN games g USING(games_id) WHERE a.noc_code IN ({ph}) GROUP BY 1", **par)
    need_rows(h, "nations")
    h = h.merge(sp, on="noc_code", how="left").merge(wm, on="noc_code", how="left").fillna(0)
    h["medals_per_appearance"] = h.total_medals / h.appearances.replace(0, np.nan)
    h["gold_ratio"] = h.gold / h.total_medals.replace(0, np.nan)
    h["athletes_per_games"] = h.athletes / h.appearances.replace(0, np.nan)
    h = h.fillna(0)
    raw = {k: h[k].astype(float) for k, _ in RADAR_AXES}
    series, table = [], []
    for i, r in h.iterrows():
        vals = {lab: (float(r[k]) / float(raw[k].max()) * 100 if raw[k].max() else 0) for k, lab in RADAR_AXES}
        series.append({"name": r.historical_name, "noc": r.noc_code, "values": vals})
        table.append({"nation": r.historical_name, **{lab: round(float(r[k]), 3) for k, lab in RADAR_AXES}})
    return payload("c_radar", "radar", {"axes": [lab for _, lab in RADAR_AXES], "series": series, "max": 100}, table=table_from(table), ctx=ctx,
                   notes=["Each axis is scaled so the largest value among the compared nations is 100; raw values are in the data table. Delegation size = athlete entries per Games attended."],
                   interpretation="Compare shapes, not areas: each axis has a different unit, so values are normalised per axis across the nations shown (the table gives the raw numbers). Pick nations with the filter.")


@chart("c_efficiency", S, "countries", "Medal efficiency (athletes vs medals)", "scatter", "Gold country medals", "gold_country_medals",
       "Show which nations convert delegation size into medals most efficiently", ("season", "year_range"), ("table",))
def efficiency(ctx: Ctx):
    d = window_medals(ctx)
    d = d[(d.athlete_entries > 0)]
    drawn = d[d.Total > 0]
    rows = [{"name": r.name, "noc": r.noc_code, "x": int(r.athlete_entries), "y": int(r.Total), "z": int(r.editions), "group": r.continent or "Neutral / unassigned",
             "per100": round(100 * r.Total / r.athlete_entries, 2)} for r in drawn.itertuples()]
    return payload("c_efficiency", "scatter", {"rows": rows, "xLabel": "Athlete entries in the window (sum over Games)", "yLabel": "Medals in the window", "logX": True, "logY": True, "sizeLabel": "Games attended",
                   "groupLabel": "Continent", "extra": ["per100"], "diag": {"label": "10 medals per 100 athletes", "slope": 0.1}}, axes={"x": "Athlete entries (log)", "y": "Medals (log)"}, ctx=ctx,
                   drill={"type": "country", "key": "noc"},
                   interpretation=f"Log-log axes because both counts span several orders of magnitude. Points above the dashed line win more than 10 medals per 100 athlete entries. "
                                  f"{len(d) - len(drawn)} NOCs with athletes but no medals are not drawn (log axis cannot show zero) and are listed in the data table only when they have medals.")


@chart("c_lorenz", S, "medals", "Medal concentration (Lorenz curve)", "lorenz", "Gold country medals x participation", "gold_country_medals",
       "Quantify how unequally medals are distributed across participating nations", ("season", "year_range"), ())
def lorenz(ctx: Ctx):
    w, par = ctx.where("g")
    part = df(f"SELECT DISTINCT p.noc_code FROM silver_participations p WHERE p.noc_code IS NOT NULL {w.replace('g.', 'p.')}", **par)
    tot = df(f"SELECT noc_code, SUM(total) m FROM gold_country_medals g WHERE 1=1 {w} GROUP BY noc_code", **par)
    d = part.merge(tot, on="noc_code", how="outer").fillna({"m": 0})
    need_rows(d, "nations")
    v = np.sort(d.m.values.astype(float))
    cum = np.insert(np.cumsum(v) / v.sum(), 0, 0)
    xs = np.linspace(0, 1, len(cum))
    idx = np.unique(np.linspace(0, len(xs) - 1, 120).astype(int))
    g = gini(v)
    top10 = np.sort(v)[::-1][:max(1, int(round(0.1 * len(v))))].sum() / v.sum()
    rows = [{"share_of_nations": round(float(xs[i]), 4), "share_of_medals": round(float(cum[i]), 4)} for i in idx]
    return payload("lorenz", "lorenz", {"rows": rows, "x": "share_of_nations", "y": "share_of_medals", "gini": g, "xLabel": "Cumulative share of nations (poorest to richest in medals)", "yLabel": "Cumulative share of medals"},
                   axes={"x": "Share of nations", "y": "Share of medals"}, ctx=ctx, table=table_from(rows),
                   interpretation=f"Gini coefficient {g:.2f} across {len(v)} participating NOCs (0 = medals spread equally, 1 = one nation wins everything). The top 10% of nations win {100 * top10:.0f}% of medals. "
                                  "NOCs that took part but won nothing are included at zero.", title="Medal concentration (Lorenz curve)")


@chart("c_pareto", S, "medals", "Pareto chart of medals by nation", "pareto", "Gold country medals", "gold_country_medals",
       "Show the 80/20 pattern of medal winning", ("season", "year_range", "top"), ("bar",))
def pareto(ctx: Ctx):
    d = window_medals(ctx)
    d = d[d.Total > 0].reset_index(drop=True)
    d["cum"] = d.Total.cumsum() / d.Total.sum()
    n = min(ctx.top or 25, 40)
    k80 = int((d.cum < 0.8).sum() + 1)
    rows = [{"name": r.noc_code, "full": r.name, "medals": int(r.Total), "cumulative_share": round(float(r.cum), 4)} for r in d.head(n).itertuples()]
    return payload("c_pareto", "pareto", {"rows": rows, "x": "name", "bar": "medals", "line": "cumulative_share", "barLabel": "Medals", "lineLabel": "Cumulative share of all medals", "pickKey": "name"},
                   axes={"x": "NOC", "y": "Medals"}, ctx=ctx, drill={"type": "country", "key": "name"}, table=table_from(rows),
                   interpretation=f"{k80} of {len(d)} medal-winning NOCs account for 80% of all medals. Bars are medals (left axis); the line is the cumulative share (right axis, 0-100%).")


@chart("c_rank_heatmap", S, "countries", "Country ranking heatmap", "heatmap", "Gold country medals", "gold_country_medals",
       "Show each leading nation's official rank at every Games at a glance", ("season", "year_range", "top"), ("bump",))
def rank_heatmap(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    nocs = top_nocs(c, ctx.top or 20, by="total")
    w, par = c.where()
    d = df(f"SELECT year, noc_code, official_rank FROM gold_country_medals WHERE noc_code IN ({','.join(f':n{i}' for i in range(len(nocs)))}) AND official_rank IS NOT NULL {w}",
           **par, **{f"n{i}": n for i, n in enumerate(nocs)})
    need_rows(d, "ranks")
    years = sorted(df(f"SELECT DISTINCT year FROM gold_country_medals WHERE 1=1 {w}", **par).year.tolist())
    rows = [{"r": r.noc_code, "c": str(int(r.year)), "v": int(r.official_rank), "label": f"{r.noc_code} {int(r.year)}: rank {int(r.official_rank)}"} for r in d.itertuples()]
    return payload("c_rank_heatmap", "heatmap", {"rows": rows, "rowOrder": nocs, "colOrder": [str(y) for y in years], "scale": "seqrev", "vLabel": "Official rank (1 = best)", "format": "int", "clipMax": 30},
                   axes={"x": "Games year", "y": "NOC"}, ctx=ctx, drill={"type": "country", "key": "r"},
                   interpretation="Bright cells are top ranks. Blank cells mean the NOC won no medals (or did not take part) that year. Colour is capped at rank 30 so mid-table positions stay distinguishable.")


@chart("c_choropleth", S, "countries", "Medals by country (choropleth)", "map", "Gold country medals x ISO codes", "gold_country_medals",
       "Show the geography of medal winning", ("season", "year_range"), ("bar",))
def choropleth(ctx: Ctx):
    d = window_medals(ctx)
    rows = [{"noc": r.noc_code, "iso3": r.iso3, "name": r.name, "v": int(r.Total)} for r in d.itertuples()]
    unmapped = [r for r in rows if not r["iso3"] and r["v"] > 0]
    return payload("c_choropleth", "map", {"frames": [{"label": _window_label(ctx), "rows": rows}], "vLabel": "Medals"}, ctx=ctx, table=table_from(rows), drill={"type": "country", "key": "noc"},
                   notes=[f"{len(unmapped)} historical or neutral delegations without a modern ISO code are not drawn: " + ", ".join(f"{r['name']} ({r['v']})" for r in unmapped[:8])] if unmapped else [],
                   interpretation="Colour scale is square-root compressed so mid-sized medal tallies remain visible next to the United States. Modern borders are drawn, so historical states (USSR, East Germany, ...) are not shown on the map.")


@chart("c_map_animated", S, "countries", "Animated historical medal map", "map", "Gold country medals x ISO codes", "gold_country_medals",
       "Show how the geography of accumulated medals evolved edition by edition", ("season", "year_range"), ())
def map_animated(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    w, par = c.where("g")
    d = df(f"SELECT g.year, g.noc_code, h.historical_name name, h.iso_alpha3 iso3, g.total FROM gold_country_medals g LEFT JOIN historical_nocs h USING(noc_code) WHERE 1=1 {w}", **par)
    need_rows(d, "medals")
    years = sorted(d.year.unique())
    cum, frames = {}, []
    meta = d.drop_duplicates("noc_code").set_index("noc_code")[["name", "iso3"]].to_dict("index")
    for y in years:
        for r in d[d.year == y].itertuples():
            cum[r.noc_code] = cum.get(r.noc_code, 0) + int(r.total)
        frames.append({"label": f"Through {int(y)}", "rows": [{"noc": k, "iso3": meta[k]["iso3"], "name": meta[k]["name"], "v": v} for k, v in cum.items()]})
    return payload("c_map_animated", "map", {"frames": frames, "vLabel": f"Cumulative {(c.season or 'summer')} medals", "animate": True, "fixedScale": True}, ctx=ctx,
                   table=table_from([{"through_year": f["label"], **r} for f in frames[-1:] for r in f["rows"]]), drill={"type": "country", "key": "noc"},
                   interpretation="Press play to step through the Games. The colour scale is fixed to the final frame, so colours are comparable across frames. The table lists the final frame.")


@chart("c_bubble", S, "countries", "Country performance bubbles", "scatter", "Participation history", "gold_country_participation_history",
       "Relate delegation size, medal yield and total medals for every nation", (), ("table",))
def bubble(ctx: Ctx):
    d = df("SELECT noc_code, historical_name, continent, appearances, athletes, total_medals, gold FROM gold_country_participation_history WHERE appearances>0 AND athletes>0")
    d = d[d.total_medals > 0]
    need_rows(d, "nations")
    rows = [{"name": r.historical_name, "noc": r.noc_code, "x": round(r.athletes / r.appearances, 1), "y": round(r.total_medals / r.appearances, 2), "z": int(r.total_medals),
             "group": r.continent or "Neutral / unassigned", "appearances": int(r.appearances)} for r in d.itertuples()]
    return payload("c_bubble", "scatter", {"rows": rows, "xLabel": "Athletes per Games attended", "yLabel": "Medals per Games attended", "logX": True, "logY": True, "sizeLabel": "Total medals", "groupLabel": "Continent",
                   "extra": ["appearances"]}, axes={"x": "Athletes per Games (log)", "y": "Medals per Games (log)"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation="Bubble area is total medals. Nations towards the top-left reach the podium with comparatively small delegations; log axes keep tiny and huge delegations on one readable scale. "
                                  "Only nations with at least one medal are drawn.")
